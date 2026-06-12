import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy

from langbot.pkg.api.http.service.sales import SalesService, YUANFUDAO_CATALOG_PRODUCTS
from langbot_plugin.api.entities.builtin.platform import message as platform_message


def test_classify_intent_detects_handoff_request():
    service = SalesService(SimpleNamespace())

    result = service.classify_intent('这个报价我想找人工销售确认一下，能转人工吗？')

    assert result['intent'] == 'handoff'
    assert result['requires_handoff'] is True
    assert result['confidence'] >= 0.8


def test_normalize_sales_message_content_preserves_text_image_voice_and_source_metadata():
    service = SalesService(SimpleNamespace())
    raw = json.dumps(
        [
            {'type': 'Source', 'id': 'source-1', 'timestamp': 1781173324},
            {'type': 'Plain', 'text': '你好'},
            {'type': 'Image', 'url': 'https://example.com/a.png', 'name': 'a.png'},
            {'type': 'Voice', 'base64': 'data:audio/ogg;base64,AAAA', 'length': 3},
        ],
        ensure_ascii=False,
    )

    normalized = service.normalize_sales_message_content(raw)

    assert normalized['preview'] == '你好 [图片] [语音]'
    assert [part['kind'] for part in normalized['components']] == ['text', 'image', 'voice']
    assert normalized['components'][1]['url'] == 'https://example.com/a.png'
    assert normalized['components'][2]['base64'].startswith('data:audio/ogg;base64,')
    assert normalized['metadata']['source']['id'] == 'source-1'


def test_normalize_sales_message_content_keeps_unavailable_media_as_real_attachment():
    service = SalesService(SimpleNamespace())
    raw = json.dumps(
        [
            {'type': 'Voice', 'voice_id': 'file_v3_001', 'url': '', 'path': '', 'base64': ''},
            {'type': 'Image', 'image_id': 'img_001'},
        ],
        ensure_ascii=False,
    )

    normalized = service.normalize_sales_message_content(raw)

    assert normalized['preview'] == '[语音] [图片]'
    assert normalized['components'][0]['kind'] == 'voice'
    assert normalized['components'][0]['available'] is False
    assert normalized['components'][0]['raw']['voice_id'] == 'file_v3_001'
    assert normalized['components'][1]['kind'] == 'image'
    assert normalized['components'][1]['available'] is False
    assert normalized['components'][1]['raw']['image_id'] == 'img_001'


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


class _ColumnRow:
    def __init__(self, **values):
        self._values = values
        self._mapping = values

    def __getitem__(self, index):
        return list(self._values.values())[index]


@pytest.mark.asyncio
async def test_get_sales_conversations_uses_latest_real_monitoring_message_not_memory_summary():
    session = SimpleNamespace(
        session_id='person_customer-1',
        bot_id='bot-uuid',
        bot_name='销售数字员工',
        pipeline_id='pipe-1',
        pipeline_name='销售流程',
        message_count=2,
        start_time=datetime.datetime(2026, 6, 12, 9, 0, 0),
        last_activity=datetime.datetime(2026, 6, 12, 9, 2, 0),
        is_active=True,
        platform='person',
        user_id='customer-1',
        user_name='客户A',
    )
    message = SimpleNamespace(
        id='msg-2',
        timestamp=datetime.datetime(2026, 6, 12, 9, 2, 0),
        session_id='person_customer-1',
        role='assistant',
        message_content=json.dumps([{'type': 'Plain', 'text': '真实AI回复'}], ensure_ascii=False),
        bot_id='bot-uuid',
        bot_name='销售数字员工',
        pipeline_id='pipe-1',
        pipeline_name='销售流程',
        status='success',
        level='info',
        platform='person',
        user_id='customer-1',
        user_name='客户A',
        runner_name='',
        variables=None,
    )
    memory = SimpleNamespace(
        session_id='person_customer-1',
        customer_name='客户A',
        summary='这不是聊天记录',
        stage='new',
        last_intent='general',
        profile={},
        intents=[],
        last_seen_at=datetime.datetime(2026, 6, 12, 9, 1, 0),
    )
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(
            side_effect=[
                _FakeResult([session]),
                _FakeResult([message]),
                _FakeResult([memory]),
                _FakeResult([]),
            ]
        ),
        serialize_model=lambda _model, value: value.__dict__,
    )
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    conversations = await service.get_sales_conversations()

    assert conversations[0]['session_id'] == 'person_customer-1'
    assert conversations[0]['latest_message_preview'] == '真实AI回复'
    assert conversations[0]['latest_message_preview'] != '这不是聊天记录'
    assert conversations[0]['handoff_status'] == 'ai_hosted'


@pytest.mark.asyncio
async def test_get_sales_conversations_handles_column_rows_from_connection_execute():
    session = _ColumnRow(
        session_id='person_customer-1',
        bot_id='bot-uuid',
        bot_name='销售数字员工',
        pipeline_id='pipe-1',
        pipeline_name='销售流程',
        message_count=2,
        start_time=datetime.datetime(2026, 6, 12, 9, 0, 0),
        last_activity=datetime.datetime(2026, 6, 12, 9, 2, 0),
        is_active=True,
        platform='person',
        user_id='customer-1',
        user_name='客户A',
    )
    message = _ColumnRow(
        id='msg-2',
        timestamp=datetime.datetime(2026, 6, 12, 9, 2, 0),
        session_id='person_customer-1',
        role='user',
        message_content=json.dumps([{'type': 'Plain', 'text': '刚发的新消息'}], ensure_ascii=False),
        bot_id='bot-uuid',
        bot_name='销售数字员工',
        pipeline_id='pipe-1',
        pipeline_name='销售流程',
        status='success',
        level='info',
        platform='person',
        user_id='customer-1',
        user_name='客户A',
        runner_name='',
        variables=None,
    )
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(
            side_effect=[
                _FakeResult([session]),
                _FakeResult([message]),
                _FakeResult([]),
                _FakeResult([]),
            ]
        ),
        serialize_model=lambda _model, value: value.__dict__,
    )
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    conversations = await service.get_sales_conversations()

    assert conversations[0]['session_id'] == 'person_customer-1'
    assert conversations[0]['latest_message_preview'] == '刚发的新消息'


@pytest.mark.asyncio
async def test_get_sales_conversation_messages_returns_ordered_components_and_sender_kind():
    user_message = SimpleNamespace(
        id='msg-1',
        timestamp=datetime.datetime(2026, 6, 12, 9, 1, 0),
        session_id='person_customer-1',
        role='user',
        message_content=json.dumps([{'type': 'Plain', 'text': '用户消息'}], ensure_ascii=False),
        bot_id='bot-uuid',
        bot_name='销售数字员工',
        pipeline_id='pipe-1',
        pipeline_name='销售流程',
        status='success',
        level='info',
        platform='person',
        user_id='customer-1',
        user_name='客户A',
        runner_name='',
        variables=None,
    )
    operator_message = SimpleNamespace(
        **{
            **user_message.__dict__,
            'id': 'msg-2',
            'timestamp': datetime.datetime(2026, 6, 12, 9, 2, 0),
            'role': 'assistant',
            'message_content': json.dumps([{'type': 'Plain', 'text': '人工消息'}], ensure_ascii=False),
            'runner_name': 'sales-admin',
            'variables': json.dumps({'sales_sender_kind': 'operator'}, ensure_ascii=False),
        }
    )
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(return_value=_FakeResult([operator_message, user_message])),
        serialize_model=lambda _model, value: value.__dict__,
    )
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    result = await service.get_sales_conversation_messages('person_customer-1')

    assert [message['id'] for message in result['messages']] == ['msg-1', 'msg-2']
    assert result['messages'][0]['sender_kind'] == 'customer'
    assert result['messages'][1]['sender_kind'] == 'operator'
    assert result['messages'][1]['components'][0]['text'] == '人工消息'


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
            {'type': 'image', 'file_key': 'course-sales/phonics/gift_poster.jpeg'},
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


class _ConversationPersistence:
    def __init__(self, session=None, handoff=None):
        self.session = session
        self.handoff = handoff
        self.statements = []

    async def execute_async(self, statement):
        self.statements.append(statement)
        text = str(statement)
        if 'monitoring_sessions' in text:
            return _FakeResult(self.session)
        if 'sales_handoffs' in text and 'SELECT' in text.upper():
            return _FakeResult(self.handoff)
        return _FakeResult(None)


@pytest.mark.asyncio
async def test_send_operator_message_from_session_does_not_create_handoff_when_ai_hosted():
    session = SimpleNamespace(
        session_id='person_customer-1',
        bot_id='bot-uuid',
        bot_name='销售数字员工',
        pipeline_id='pipe-1',
        pipeline_name='销售流程',
        platform='person',
        user_id='customer-1',
        user_name='客户A',
    )
    adapter = _CaptureAdapter()
    monitoring_service = SimpleNamespace(record_message=AsyncMock(return_value='manual-msg-id'))
    persistence_mgr = _ConversationPersistence(session=session)
    service = SalesService(
        SimpleNamespace(
            persistence_mgr=persistence_mgr,
            platform_mgr=_CapturePlatformManager(adapter),
            monitoring_service=monitoring_service,
        )
    )

    result = await service.send_operator_message_from_session(
        'person_customer-1',
        '人工主动补充一句',
        assigned_to='sales-admin',
        pause_ai=False,
    )

    assert result['sent'] is True
    assert result['handoff_id'] is None
    assert adapter.sent[0][0] == 'person'
    assert adapter.sent[0][1] == 'customer-1'
    monitoring_service.record_message.assert_awaited_once()
    assert not any('INSERT INTO sales_handoffs' in str(statement) for statement in persistence_mgr.statements)


@pytest.mark.asyncio
async def test_reply_handoff_keeps_status_open_so_ai_stays_paused():
    handoff = SimpleNamespace(
        id=7,
        session_id='person_customer-1',
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='customer-1',
        platform='person',
        user_id='customer-1',
        status='open',
    )
    adapter = _CaptureAdapter()
    persistence_mgr = SimpleNamespace(execute_async=AsyncMock(side_effect=[_FakeResult(handoff), _FakeResult(None)]))
    service = SalesService(
        SimpleNamespace(
            persistence_mgr=persistence_mgr,
            platform_mgr=_CapturePlatformManager(adapter),
            monitoring_service=SimpleNamespace(record_message=AsyncMock(return_value='manual-msg-id')),
        )
    )

    await service.reply_handoff(7, '人工处理中回复', 'sales-admin')

    update_statement = persistence_mgr.execute_async.await_args_list[-1].args[0]
    update_values = dict(update_statement.compile().params)
    assert update_values['status'] == 'open'
    assert update_values['operator_reply'] == '人工处理中回复'


@pytest.mark.asyncio
async def test_restore_ai_hosting_closes_open_handoff():
    handoff = SimpleNamespace(id=7, session_id='person_customer-1', status='open', assigned_to='')
    persistence_mgr = SimpleNamespace(execute_async=AsyncMock(side_effect=[_FakeResult(handoff), _FakeResult(None)]))
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    result = await service.restore_ai_hosting_from_session('person_customer-1', 'sales-admin')

    assert result == {'restored': True, 'handoff_id': 7}
    update_statement = persistence_mgr.execute_async.await_args_list[-1].args[0]
    update_values = dict(update_statement.compile().params)
    assert update_values['status'] == 'ai_resumed'


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


@pytest.mark.asyncio
async def test_get_product_returns_serialized_product():
    product_row = SimpleNamespace(
        uuid='product-1',
        name='AI 销售助手',
        category='sales',
        price='299/月',
        link='https://example.com',
        description='desc',
        selling_points=['卖点'],
        pain_points=[],
        objections=[],
        audience=[],
        enabled=True,
        created_at=None,
        updated_at=None,
    )
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(return_value=_FakeResult(product_row)),
        serialize_model=lambda _model, row: {
            'uuid': row.uuid,
            'name': row.name,
            'category': row.category,
            'price': row.price,
            'link': row.link,
            'description': row.description,
            'selling_points': row.selling_points,
            'pain_points': row.pain_points,
            'objections': row.objections,
            'audience': row.audience,
            'enabled': row.enabled,
        },
    )
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    result = await service.get_product('product-1')

    assert result['uuid'] == 'product-1'
    assert result['name'] == 'AI 销售助手'


@pytest.mark.asyncio
async def test_get_product_raises_when_missing():
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(return_value=_FakeResult(None)),
    )
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    with pytest.raises(ValueError, match='Product not found'):
        await service.get_product('missing-product')


@pytest.mark.asyncio
async def test_create_product_requires_name():
    service = SalesService(SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=AsyncMock())))

    with pytest.raises(ValueError, match='Product name is required'):
        await service.create_product({'name': '   '})


def test_clean_product_payload_supports_product_line_fields():
    service = SalesService(SimpleNamespace())

    payload = service._clean_product_payload(
        {
            'name': '猿辅导阅读+思维特训营',
            'product_line': '猿辅导',
            'profile_key': 'reading_thinking',
            'keywords': ['阅读', '思维'],
            'category': '阅读+思维',
            'price': '9元体验',
        }
    )

    assert payload['product_line'] == '猿辅导'
    assert payload['profile_key'] == 'reading_thinking'
    assert payload['keywords'] == ['阅读', '思维']


def test_yuanfudao_catalog_products_include_reading_thinking_course():
    products_by_uuid = {product['uuid']: product for product in YUANFUDAO_CATALOG_PRODUCTS}

    assert set(products_by_uuid) == {
        'yuanfudao-phonics-course',
        'yuanfudao-reading-thinking-course',
    }
    assert products_by_uuid['yuanfudao-phonics-course']['product_line'] == '猿辅导'
    assert products_by_uuid['yuanfudao-reading-thinking-course']['profile_key'] == 'reading_thinking'


def test_build_radar_tracking_url_wraps_destination_with_token():
    service = SalesService(
        SimpleNamespace(
            instance_config={'api': {'host': '127.0.0.1', 'port': 5300}},
        )
    )

    url = service.build_radar_tracking_url(
        destination_url='https://m.yuanfudao.com/apply',
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='customer-1',
        link_id='phonics_radar_apply',
        session_id='person_customer-1',
    )

    assert url.startswith('http://127.0.0.1:5300/api/v1/sales/radar/click/')
    payload = service.decode_radar_tracking_token(url.rsplit('/', 1)[-1])
    assert payload['d'] == 'https://m.yuanfudao.com/apply'
    assert payload['b'] == 'bot-uuid'
    assert payload['i'] == 'customer-1'


def test_build_radar_tracking_url_uses_public_base_url_when_configured():
    service = SalesService(
        SimpleNamespace(
            instance_config={
                'api': {'host': '127.0.0.1', 'port': 5300},
                'sales': {'radar_public_base_url': 'https://bot.example.com/base/'},
            },
        )
    )

    url = service.build_radar_tracking_url(
        destination_url='https://m.yuanfudao.com/primary/templates/package?pageId=6641',
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='customer-1',
    )

    assert url.startswith('https://bot.example.com/base/api/v1/sales/radar/click/')


@pytest.mark.asyncio
async def test_handle_radar_tracking_click_schedules_followup_and_returns_destination():
    task_assistant = SimpleNamespace(handle_course_sales_radar_event=AsyncMock(return_value={'handled': True}))
    service = SalesService(
        SimpleNamespace(
            task_assistant_service=task_assistant,
            logger=_SilentLogger(),
            instance_config={'api': {'host': '127.0.0.1', 'port': 5300}},
        )
    )
    token = service.build_radar_tracking_url(
        destination_url='https://m.yuanfudao.com/apply',
        bot_uuid='bot-uuid',
        target_type='person',
        target_id='customer-1',
        link_id='phonics_radar_apply',
        session_id='person_customer-1',
        event='link_open',
    ).rsplit('/', 1)[-1]

    destination = await service.handle_radar_tracking_click(token)

    assert destination == 'https://m.yuanfudao.com/apply'
    task_assistant.handle_course_sales_radar_event.assert_awaited_once()
