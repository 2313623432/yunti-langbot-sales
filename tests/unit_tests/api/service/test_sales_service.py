from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy

from langbot.pkg.api.http.service.sales import SalesService
from langbot_plugin.api.entities.builtin.platform import message as platform_message


def test_classify_intent_detects_handoff_request():
    service = SalesService(SimpleNamespace())

    result = service.classify_intent('这个报价我想找人工销售确认一下，能转人工吗？')

    assert result['intent'] == 'handoff'
    assert result['requires_handoff'] is True
    assert result['confidence'] >= 0.8


def test_select_best_product_matches_selling_points_and_pain_points():
    service = SalesService(SimpleNamespace())
    products = [
        {
            'uuid': 'crm',
            'name': 'AI CRM',
            'category': 'sales',
            'selling_points': ['客户分层', '自动跟进', '销售线索评分'],
            'pain_points': ['线索太多跟不过来'],
            'audience': ['销售团队'],
        },
        {
            'uuid': 'finance',
            'name': '智能财务助手',
            'category': 'finance',
            'selling_points': ['自动报销', '票据识别'],
            'pain_points': ['发票整理麻烦'],
            'audience': ['财务团队'],
        },
    ]

    result = service.select_best_product('我们销售团队线索太多，客户跟进经常漏掉', products)

    assert result is not None
    assert result['uuid'] == 'crm'


def test_generate_pitch_uses_selling_points_link_and_customer_context():
    service = SalesService(SimpleNamespace())
    product = {
        'name': 'AI 销售助手',
        'price': '299/月',
        'link': 'https://example.com/ai-sales',
        'selling_points': ['自动识别客户意图', '按产品卖点生成回复', '高意向客户转人工'],
        'pain_points': ['销售回复不及时', '客户意向难判断'],
    }

    result = service.generate_pitch(
        product,
        customer_profile='客户是教育行业负责人，关注转化率',
        intent='对自动销售感兴趣',
    )

    assert 'AI 销售助手' in result['message']
    assert '自动识别客户意图' in result['message']
    assert 'https://example.com/ai-sales' in result['message']
    assert result['next_action'] == 'send_product_link'


def test_compose_sales_prompt_includes_product_memory_and_handoff_policy():
    service = SalesService(SimpleNamespace())

    prompt = service.compose_sales_prompt(
        product={
            'name': 'AI 销售助手',
            'selling_points': ['自动跟进', '转人工'],
            'link': 'https://example.com',
        },
        memory={'summary': '客户预算明确，正在比较竞品', 'stage': 'consideration'},
        intent={'intent': 'comparison', 'requires_handoff': False},
    )

    assert 'AI 销售助手' in prompt
    assert '客户预算明确' in prompt
    assert 'comparison' in prompt
    assert '客户明确要求人工' in prompt


@pytest.mark.asyncio
async def test_prepare_query_keeps_existing_open_handoff_in_manual_mode(monkeypatch):
    app = SimpleNamespace(logger=SimpleNamespace(warning=lambda *_args, **_kwargs: None))
    service = SalesService(app)
    query = SimpleNamespace(
        variables={'user_message_text': '我还在等人工'},
        launcher_type=SimpleNamespace(value='person'),
        launcher_id='ou_customer',
        sender_id='ou_customer',
        bot_uuid='bot-uuid',
        adapter=SimpleNamespace(),
        prompt=SimpleNamespace(messages=[]),
    )
    get_open_handoff = AsyncMock(return_value={'id': 7, 'reason': '客户要求人工介入'})
    refresh_handoff = AsyncMock(return_value={'id': 7})

    monkeypatch.setattr(service, 'get_open_handoff_for_query', get_open_handoff, raising=False)
    monkeypatch.setattr(service, 'open_handoff_from_query', refresh_handoff)
    monkeypatch.setattr(service, 'get_products', AsyncMock(return_value=[]))
    monkeypatch.setattr(service, 'upsert_memory_from_query', AsyncMock(return_value={}))

    result = await service.prepare_query(query)

    assert result['interrupted'] is True
    assert '人工' in result['notice']
    get_open_handoff.assert_awaited_once_with(query)
    refresh_handoff.assert_awaited_once_with(query, '客户要求人工介入', '我还在等人工')


class _FakeResult:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row

    def all(self):
        if self.row is None:
            return []
        if isinstance(self.row, list):
            return self.row
        return [self.row]


class _SilentLogger:
    def warning(self, *_args, **_kwargs):
        pass


class _FakeStorageProvider:
    async def load(self, _file_key):
        return b'image-bytes'


@pytest.mark.asyncio
async def test_build_outreach_message_chain_supports_plain_link_and_image_without_voice():
    service = SalesService(
        SimpleNamespace(
            storage_mgr=SimpleNamespace(storage_provider=_FakeStorageProvider()),
            logger=_SilentLogger(),
        )
    )
    plan = SimpleNamespace(
        message_template='',
        message_components=[
            {'type': 'plain', 'text': '家长您好'},
            {
                'type': 'link',
                'title': '报名链接卡片',
                'description': '9元体验课报名通道',
                'url': 'https://example.com/apply',
            },
            {'type': 'image', 'file_key': 'course-sales/phonics/phonics_poster.jpeg'},
        ],
    )

    chain = await service._build_outreach_message_chain(plan, {})

    assert any(isinstance(component, platform_message.Plain) and component.text == '家长您好' for component in chain)
    assert any(isinstance(component, platform_message.WeChatLink) and component.link_url == 'https://example.com/apply' for component in chain)
    assert any(isinstance(component, platform_message.Image) and component.base64.startswith('data:image/jpeg;base64,') for component in chain)
    assert not any(isinstance(component, platform_message.Voice) for component in chain)


class _CaptureAdapter:
    def __init__(self):
        self.sent = []

    async def send_message(self, target_type, target_id, message_chain):
        self.sent.append((target_type, target_id, message_chain))


class _CapturePlatformManager:
    def __init__(self, adapter):
        self.adapter = adapter

    async def get_bot_by_uuid(self, _bot_uuid):
        return SimpleNamespace(adapter=self.adapter)


class _OutreachPersistence:
    def __init__(self, plan):
        self.plan = plan
        self.update_values = None

    async def execute_async(self, statement):
        if getattr(statement, 'is_update', False):
            self.update_values = dict(statement.compile().params)
            return _FakeResult(None)
        return _FakeResult([self.plan])


@pytest.mark.asyncio
async def test_run_due_outreach_once_sends_components_and_marks_one_shot_disabled(monkeypatch):
    plan = SimpleNamespace(
        id=12,
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='customer-1',
        product_uuid='',
        message_template='',
        message_components=[{'type': 'plain', 'text': 'SOP定时群发内容'}],
        interval_minutes=0,
    )
    adapter = _CaptureAdapter()
    persistence_mgr = _OutreachPersistence(plan)
    service = SalesService(
        SimpleNamespace(
            persistence_mgr=persistence_mgr,
            platform_mgr=_CapturePlatformManager(adapter),
            logger=_SilentLogger(),
        )
    )
    monkeypatch.setattr(service, 'get_products', AsyncMock(return_value=[]))

    sent = await service.run_due_outreach_once()

    assert sent == 1
    assert adapter.sent[0][0] == 'person'
    assert adapter.sent[0][1] == 'customer-1'
    assert any(component.text == 'SOP定时群发内容' for component in adapter.sent[0][2] if isinstance(component, platform_message.Plain))
    assert persistence_mgr.update_values['enabled'] is False


@pytest.mark.asyncio
async def test_get_chatted_outreach_targets_uses_sessions_with_user_messages():
    sessions = [
        SimpleNamespace(
            session_id='person_customer-1',
            bot_id='bot-uuid',
            pipeline_id='course-sales-template-pipeline',
            platform='person',
            user_id='customer-1',
        ),
        SimpleNamespace(
            session_id='person_customer-1',
            bot_id='bot-uuid',
            pipeline_id='course-sales-template-pipeline',
            platform='person',
            user_id='customer-1',
        ),
        SimpleNamespace(
            session_id='group_room-1',
            bot_id='bot-uuid',
            pipeline_id='course-sales-template-pipeline',
            platform='group',
            user_id='customer-2',
        ),
    ]
    persistence_mgr = SimpleNamespace(execute_async=AsyncMock(return_value=_FakeResult(sessions)))
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    targets = await service.get_chatted_outreach_targets(pipeline_uuids=['course-sales-template-pipeline'])

    assert targets == [
        {
            'bot_uuid': 'bot-uuid',
            'target_type': 'person',
            'target_id': 'customer-1',
            'session_id': 'person_customer-1',
            'pipeline_uuid': 'course-sales-template-pipeline',
            'user_id': 'customer-1',
        },
        {
            'bot_uuid': 'bot-uuid',
            'target_type': 'group',
            'target_id': 'room-1',
            'session_id': 'group_room-1',
            'pipeline_uuid': 'course-sales-template-pipeline',
            'user_id': 'customer-2',
        },
    ]


class _FakePersistenceManager:
    def __init__(self, handoff):
        self.handoff = handoff
        self.update_count = 0

    async def execute_async(self, statement):
        if getattr(statement, 'is_update', False):
            self.update_count += 1
        return _FakeResult(self.handoff)


class _MissingPlatformManager:
    async def get_bot_by_uuid(self, _bot_uuid):
        return None


@pytest.mark.asyncio
async def test_reply_handoff_does_not_close_when_runtime_bot_is_missing():
    handoff = SimpleNamespace(
        id=7,
        bot_uuid='missing-bot',
        target_id='ou_customer',
        target_type='person',
    )
    persistence_mgr = _FakePersistenceManager(handoff)
    service = SalesService(
        SimpleNamespace(
            persistence_mgr=persistence_mgr,
            platform_mgr=_MissingPlatformManager(),
        )
    )

    with pytest.raises(ValueError, match='not running'):
        await service.reply_handoff(7, '人工已接入', 'sales-admin')

    assert persistence_mgr.update_count == 0


class _DuplicateDefaultProductPersistence:
    def __init__(self):
        self.insert_count = 0

    async def execute_async(self, statement):
        if getattr(statement, 'is_insert', False):
            self.insert_count += 1
            raise sqlalchemy.exc.IntegrityError('insert sales product', {}, Exception('duplicate uuid'))
        return _FakeResult(None)


@pytest.mark.asyncio
async def test_ensure_default_products_ignores_concurrent_duplicate_inserts():
    persistence_mgr = _DuplicateDefaultProductPersistence()
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    await service.ensure_default_products()

    assert persistence_mgr.insert_count >= 1


class _SessionHandoffPersistence:
    def __init__(self, session, message, handoff=None):
        self.results = [_FakeResult(session), _FakeResult(message), _FakeResult(handoff)]
        self.insert_values = None
        self.update_values = None

    async def execute_async(self, statement):
        if getattr(statement, 'is_insert', False):
            self.insert_values = dict(statement.compile().params)
            return _FakeResult(None)
        if getattr(statement, 'is_update', False):
            self.update_values = dict(statement.compile().params)
            return _FakeResult(None)
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_open_handoff_from_monitoring_session_creates_open_handoff():
    session = SimpleNamespace(
        session_id='person_customer-1',
        bot_id='bot-uuid',
        platform='person',
        user_id='customer-1',
        user_name='Alice',
    )
    message = SimpleNamespace(message_content='I need help from sales')
    persistence_mgr = _SessionHandoffPersistence(session, message)
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    handoff = await service.open_handoff_from_session('person_customer-1', 'Manual takeover', 'sales-admin')

    assert handoff['session_id'] == 'person_customer-1'
    assert handoff['bot_uuid'] == 'bot-uuid'
    assert handoff['target_type'] == 'person'
    assert handoff['target_id'] == 'customer-1'
    assert handoff['reason'] == 'Manual takeover'
    assert handoff['last_message'] == 'I need help from sales'
    assert handoff['assigned_to'] == 'sales-admin'
    assert persistence_mgr.insert_values['status'] == 'open'


@pytest.mark.asyncio
async def test_open_handoff_from_monitoring_session_reuses_existing_open_handoff():
    session = SimpleNamespace(
        session_id='group_room-1',
        bot_id='bot-uuid',
        platform='group',
        user_id='customer-1',
        user_name='Alice',
    )
    message = SimpleNamespace(message_content='Latest customer message')
    existing = SimpleNamespace(id=9)
    persistence_mgr = _SessionHandoffPersistence(session, message, existing)
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    handoff = await service.open_handoff_from_session('group_room-1')

    assert handoff['id'] == 9
    assert handoff['target_type'] == 'group'
    assert handoff['target_id'] == 'room-1'
    assert handoff['reason'] == '人工主动介入'
    assert persistence_mgr.insert_values is None
    assert persistence_mgr.update_values['last_message'] == 'Latest customer message'


@pytest.mark.asyncio
async def test_reply_handoff_from_session_opens_then_replies(monkeypatch):
    service = SalesService(SimpleNamespace())
    open_handoff = AsyncMock(return_value={'id': 7})
    reply_handoff = AsyncMock()
    monkeypatch.setattr(service, 'open_handoff_from_session', open_handoff)
    monkeypatch.setattr(service, 'reply_handoff', reply_handoff)

    result = await service.reply_handoff_from_session('person_customer-1', '人工已接入', 'sales-admin')

    assert result == {'sent': True, 'handoff_id': 7}
    open_handoff.assert_awaited_once_with('person_customer-1', '人工直接回复', 'sales-admin')
    reply_handoff.assert_awaited_once_with(7, '人工已接入', 'sales-admin')
