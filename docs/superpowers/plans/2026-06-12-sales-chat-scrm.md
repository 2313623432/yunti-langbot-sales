# Sales Chat SCRM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a SCRM-style 聚合聊天 page backed only by real `monitoring_messages`, with image/voice rendering, manual-intervention tabs, AI recommendation drafts, and explicit AI resume control.

**Architecture:** Add normalized sales-conversation service methods on top of the existing monitoring and handoff tables, then expose them through `/api/v1/sales/conversations`. Keep historical message rows immutable. The frontend stops merging memories into fake chat rows and instead renders normalized messages/components from the new endpoints.

**Tech Stack:** Python 3.12, Quart route groups, SQLAlchemy async persistence, SQLite built-in database, pytest/pytest-asyncio, React 19, Vite, TypeScript, Tailwind CSS, lucide-react.

---

## File Structure

- Modify `src/langbot/pkg/api/http/service/sales.py`
  - Add message-chain normalization helpers.
  - Add conversation list/message query methods.
  - Add manual send, handoff reply, restore AI, and AI suggestion service methods.
  - Extend intent rules for upset-customer handoff triggers.
- Modify `src/langbot/pkg/api/http/controller/groups/sales.py`
  - Add conversation, message, manual reply, handoff start/reply/restore, and AI suggestion endpoints.
- Modify `tests/unit_tests/api/service/test_sales_service.py`
  - Add unit tests for message normalization, real previews, handoff statuses, normal manual send, and restore AI.
- Modify `tests/integration/api/test_sales.py`
  - Add endpoint tests for the new sales-conversation routes.
- Modify `web/src/app/infra/entities/api/index.ts`
  - Add normalized conversation and message component types.
- Modify `web/src/app/infra/http/BackendClient.ts`
  - Add client methods for the new endpoints.
- Create `web/src/app/home/sales-chat/message-components.tsx`
  - Render text, image, voice, file, link, quote, and unknown attachment components.
- Modify `web/src/app/home/sales-chat/page.tsx`
  - Replace mixed conversation construction with normalized API data.
  - Add tabs: 全部, AI 托管中, 待人工介入, 人工处理中.
  - Add direct manual send in AI-hosted sessions.
  - Add start handling, handoff reply, AI recommendation draft, and restore AI hosting actions.

---

### Task 1: Normalize Real Message Chains

**Files:**
- Modify: `tests/unit_tests/api/service/test_sales_service.py`
- Modify: `src/langbot/pkg/api/http/service/sales.py`

- [ ] **Step 1: Write failing tests for message normalization**

Append these tests to `tests/unit_tests/api/service/test_sales_service.py`:

```python
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
```

Also add `import json` near the top of the file if it is not already present:

```python
import json
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
uv run pytest tests/unit_tests/api/service/test_sales_service.py::test_normalize_sales_message_content_preserves_text_image_voice_and_source_metadata tests/unit_tests/api/service/test_sales_service.py::test_normalize_sales_message_content_keeps_unavailable_media_as_real_attachment -q
```

Expected: both tests fail with `AttributeError: 'SalesService' object has no attribute 'normalize_sales_message_content'`.

- [ ] **Step 3: Implement normalization helpers**

In `src/langbot/pkg/api/http/service/sales.py`, add these methods inside `class SalesService`, near the existing sales helper methods before `_query_session_id`:

```python
    def normalize_sales_message_content(self, message_content: str) -> dict[str, Any]:
        components: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        raw_content = message_content or ''
        try:
            parsed = json.loads(raw_content)
        except (TypeError, json.JSONDecodeError):
            parsed = [{'type': 'Plain', 'text': raw_content}] if raw_content else []

        if not isinstance(parsed, list):
            parsed = [{'type': 'Plain', 'text': raw_content}]

        for item in parsed:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_sales_message_component(item)
            if normalized is None:
                source_id = item.get('id')
                if item.get('type') == 'Source' and source_id:
                    metadata['source'] = {k: v for k, v in item.items() if k != 'type'}
                continue
            components.append(normalized)

        preview = self._sales_message_preview(components)
        return {'components': components, 'preview': preview, 'metadata': metadata}

    def _normalize_sales_message_component(self, component: dict[str, Any]) -> dict[str, Any] | None:
        component_type = str(component.get('type') or '').strip()
        if component_type == 'Source':
            return None
        if component_type == 'Plain':
            return {
                'kind': 'text',
                'text': str(component.get('text') or ''),
                'raw': component,
            }
        if component_type in ('At', 'AtAll'):
            label = component.get('display') or component.get('target') or 'All'
            return {'kind': 'text', 'text': f'@{label}', 'raw': component}
        if component_type == 'Image':
            url = str(component.get('url') or '')
            base64_data = str(component.get('base64') or '')
            path = str(component.get('path') or '')
            return {
                'kind': 'image',
                'url': url,
                'base64': base64_data,
                'path': path,
                'name': str(component.get('name') or component.get('file_name') or ''),
                'available': bool(url or base64_data or path),
                'raw': component,
            }
        if component_type == 'Voice':
            url = str(component.get('url') or '')
            base64_data = str(component.get('base64') or '')
            path = str(component.get('path') or '')
            return {
                'kind': 'voice',
                'url': url,
                'base64': base64_data,
                'path': path,
                'length': component.get('length') or component.get('duration') or 0,
                'available': bool(url or base64_data or path),
                'raw': component,
            }
        if component_type == 'File':
            return {
                'kind': 'file',
                'name': str(component.get('name') or component.get('file_name') or '文件'),
                'url': str(component.get('url') or ''),
                'path': str(component.get('path') or ''),
                'available': bool(component.get('url') or component.get('path')),
                'raw': component,
            }
        if component_type in ('WeChatLink', 'Link'):
            return {
                'kind': 'link',
                'title': str(component.get('title') or component.get('name') or '链接'),
                'description': str(component.get('description') or ''),
                'url': str(component.get('url') or component.get('link_url') or ''),
                'thumb_url': str(component.get('thumb_url') or component.get('image') or ''),
                'raw': component,
            }
        if component_type == 'Quote':
            origin = component.get('origin') if isinstance(component.get('origin'), list) else []
            quoted = []
            for origin_item in origin:
                if isinstance(origin_item, dict) and origin_item.get('type') == 'Plain':
                    quoted.append(str(origin_item.get('text') or ''))
            return {'kind': 'quote', 'text': '\n'.join(quoted), 'raw': component}
        return {
            'kind': 'attachment',
            'type': component_type or 'Unknown',
            'label': f'[{component_type or "Unknown"}]',
            'raw': component,
        }

    def _sales_message_preview(self, components: list[dict[str, Any]]) -> str:
        labels = []
        for component in components:
            kind = component.get('kind')
            if kind == 'text':
                text = str(component.get('text') or '').strip()
                if text:
                    labels.append(text)
            elif kind == 'image':
                labels.append('[图片]')
            elif kind == 'voice':
                labels.append('[语音]')
            elif kind == 'file':
                labels.append(f"[文件] {component.get('name') or ''}".strip())
            elif kind == 'link':
                labels.append(f"[链接] {component.get('title') or ''}".strip())
            elif kind == 'quote':
                labels.append('[引用]')
            else:
                labels.append(str(component.get('label') or '[附件]'))
        return ' '.join(label for label in labels if label).strip()
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit_tests/api/service/test_sales_service.py::test_normalize_sales_message_content_preserves_text_image_voice_and_source_metadata tests/unit_tests/api/service/test_sales_service.py::test_normalize_sales_message_content_keeps_unavailable_media_as_real_attachment -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tests/unit_tests/api/service/test_sales_service.py src/langbot/pkg/api/http/service/sales.py
git commit -m "feat: normalize sales chat message chains"
```

---

### Task 2: Add Conversation List And Message Queries

**Files:**
- Modify: `tests/unit_tests/api/service/test_sales_service.py`
- Modify: `src/langbot/pkg/api/http/service/sales.py`

- [ ] **Step 1: Write failing tests for normalized conversations**

Append these helper/result tests to `tests/unit_tests/api/service/test_sales_service.py`:

```python
class _FakeResultList:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


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
        execute_async=AsyncMock(side_effect=[
            _FakeResultList([session]),
            _FakeResultList([message]),
            _FakeResultList([memory]),
            _FakeResultList([]),
        ]),
        serialize_model=lambda _model, value: value.__dict__,
    )
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    conversations = await service.get_sales_conversations()

    assert conversations[0]['session_id'] == 'person_customer-1'
    assert conversations[0]['latest_message_preview'] == '真实AI回复'
    assert conversations[0]['latest_message_preview'] != '这不是聊天记录'
    assert conversations[0]['handoff_status'] == 'ai_hosted'


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
        execute_async=AsyncMock(return_value=_FakeResultList([operator_message, user_message])),
        serialize_model=lambda _model, value: value.__dict__,
    )
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    result = await service.get_sales_conversation_messages('person_customer-1')

    assert [message['id'] for message in result['messages']] == ['msg-1', 'msg-2']
    assert result['messages'][0]['sender_kind'] == 'customer'
    assert result['messages'][1]['sender_kind'] == 'operator'
    assert result['messages'][1]['components'][0]['text'] == '人工消息'
```

Add this import near the top if missing:

```python
import datetime
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
uv run pytest tests/unit_tests/api/service/test_sales_service.py::test_get_sales_conversations_uses_latest_real_monitoring_message_not_memory_summary tests/unit_tests/api/service/test_sales_service.py::test_get_sales_conversation_messages_returns_ordered_components_and_sender_kind -q
```

Expected: both tests fail because `get_sales_conversations` and `get_sales_conversation_messages` are not defined.

- [ ] **Step 3: Implement conversation status and sender helpers**

Add these methods inside `SalesService` in `src/langbot/pkg/api/http/service/sales.py`, near the normalization helpers:

```python
    def _normalized_handoff_status(self, handoff: Any | None) -> str:
        if handoff is None or getattr(handoff, 'status', '') != 'open':
            return 'ai_hosted'
        if getattr(handoff, 'assigned_to', '') or getattr(handoff, 'operator_reply', ''):
            return 'manual_handling'
        return 'pending_manual'

    def _sales_sender_kind(self, message: Any) -> str:
        role = getattr(message, 'role', None)
        variables = getattr(message, 'variables', None)
        if variables:
            try:
                parsed = json.loads(variables)
            except (TypeError, json.JSONDecodeError):
                parsed = {}
            if parsed.get('sales_sender_kind') == 'operator':
                return 'operator'
        if role == 'assistant':
            return 'assistant'
        return 'customer'

    def _serialize_sales_message(self, message: Any) -> dict[str, Any]:
        normalized = self.normalize_sales_message_content(getattr(message, 'message_content', '') or '')
        sender_kind = self._sales_sender_kind(message)
        if sender_kind == 'operator':
            sender_label = getattr(message, 'runner_name', '') or '人工销售'
        elif sender_kind == 'assistant':
            sender_label = getattr(message, 'bot_name', '') or '数字员工'
        else:
            sender_label = getattr(message, 'user_name', '') or getattr(message, 'user_id', '') or '客户'
        return {
            'id': getattr(message, 'id', ''),
            'timestamp': self._format_datetime(getattr(message, 'timestamp', None)),
            'session_id': getattr(message, 'session_id', ''),
            'role': getattr(message, 'role', None),
            'sender_kind': sender_kind,
            'sender_label': sender_label,
            'bot_id': getattr(message, 'bot_id', ''),
            'bot_name': getattr(message, 'bot_name', ''),
            'platform': getattr(message, 'platform', None),
            'user_id': getattr(message, 'user_id', None),
            'user_name': getattr(message, 'user_name', None),
            'runner_name': getattr(message, 'runner_name', None),
            'status': getattr(message, 'status', ''),
            'level': getattr(message, 'level', ''),
            'preview': normalized['preview'],
            'components': normalized['components'],
            'metadata': normalized['metadata'],
            'raw_message_content': getattr(message, 'message_content', ''),
        }

    def _format_datetime(self, value: Any) -> str:
        if value is None:
            return ''
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        return str(value)
```

- [ ] **Step 4: Implement conversation queries**

Add these methods inside `SalesService`:

```python
    async def get_sales_conversations(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        session_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringSession)
            .order_by(persistence_monitoring.MonitoringSession.last_activity.desc())
            .limit(limit)
            .offset(offset)
        )
        sessions = [row[0] if isinstance(row, tuple) else row for row in session_result.all()]
        session_ids = [session.session_id for session in sessions]
        if not session_ids:
            return []

        message_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.session_id.in_(session_ids))
            .order_by(persistence_monitoring.MonitoringMessage.timestamp.desc())
        )
        latest_by_session: dict[str, Any] = {}
        for row in message_result.all():
            message = row[0] if isinstance(row, tuple) else row
            latest_by_session.setdefault(message.session_id, message)

        memory_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesCustomerMemory).where(
                persistence_sales.SalesCustomerMemory.session_id.in_(session_ids)
            )
        )
        memories = {
            (row[0] if isinstance(row, tuple) else row).session_id: row[0] if isinstance(row, tuple) else row
            for row in memory_result.all()
        }

        handoff_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesHandoff).where(
                persistence_sales.SalesHandoff.session_id.in_(session_ids)
            )
        )
        handoffs: dict[str, Any] = {}
        for row in handoff_result.all():
            handoff = row[0] if isinstance(row, tuple) else row
            current = handoffs.get(handoff.session_id)
            if current is None or getattr(handoff, 'updated_at', None) > getattr(current, 'updated_at', None):
                handoffs[handoff.session_id] = handoff

        conversations: list[dict[str, Any]] = []
        for session in sessions:
            handoff = handoffs.get(session.session_id)
            normalized_status = self._normalized_handoff_status(handoff)
            if status and status != 'all' and normalized_status != status:
                continue
            latest_message = latest_by_session.get(session.session_id)
            latest = self._serialize_sales_message(latest_message) if latest_message else None
            memory = memories.get(session.session_id)
            conversations.append(
                {
                    'session_id': session.session_id,
                    'customer_name': getattr(memory, 'customer_name', '') or getattr(session, 'user_name', '') or getattr(session, 'user_id', '') or session.session_id,
                    'platform': getattr(session, 'platform', '') or '',
                    'user_id': getattr(session, 'user_id', '') or '',
                    'user_name': getattr(session, 'user_name', '') or '',
                    'bot_id': getattr(session, 'bot_id', '') or '',
                    'bot_name': getattr(session, 'bot_name', '') or '',
                    'message_count': getattr(session, 'message_count', 0) or 0,
                    'last_activity': self._format_datetime(getattr(session, 'last_activity', None)),
                    'latest_message': latest,
                    'latest_message_preview': latest['preview'] if latest else '',
                    'handoff_status': normalized_status,
                    'handoff': self.ap.persistence_mgr.serialize_model(persistence_sales.SalesHandoff, handoff) if handoff else None,
                    'memory': self.ap.persistence_mgr.serialize_model(persistence_sales.SalesCustomerMemory, memory) if memory else None,
                }
            )
        return conversations

    async def get_sales_conversation_messages(
        self,
        session_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.session_id == session_id)
            .order_by(persistence_monitoring.MonitoringMessage.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = [row[0] if isinstance(row, tuple) else row for row in result.all()]
        messages = [self._serialize_sales_message(message) for message in sorted(rows, key=lambda item: item.timestamp)]
        return {'messages': messages, 'total': len(messages)}
```

- [ ] **Step 5: Run the tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit_tests/api/service/test_sales_service.py::test_get_sales_conversations_uses_latest_real_monitoring_message_not_memory_summary tests/unit_tests/api/service/test_sales_service.py::test_get_sales_conversation_messages_returns_ordered_components_and_sender_kind -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

```powershell
git add tests/unit_tests/api/service/test_sales_service.py src/langbot/pkg/api/http/service/sales.py
git commit -m "feat: add normalized sales conversations"
```

---

### Task 3: Implement Manual Send, Handoff Reply, And Restore AI

**Files:**
- Modify: `tests/unit_tests/api/service/test_sales_service.py`
- Modify: `src/langbot/pkg/api/http/service/sales.py`

- [ ] **Step 1: Write failing tests for manual state behavior**

Append these tests to `tests/unit_tests/api/service/test_sales_service.py`:

```python
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
    handoff = SimpleNamespace(id=7, session_id='person_customer-1', status='open')
    persistence_mgr = SimpleNamespace(execute_async=AsyncMock(side_effect=[_FakeResult(handoff), _FakeResult(None)]))
    service = SalesService(SimpleNamespace(persistence_mgr=persistence_mgr))

    result = await service.restore_ai_hosting_from_session('person_customer-1', 'sales-admin')

    assert result == {'restored': True, 'handoff_id': 7}
    update_statement = persistence_mgr.execute_async.await_args_list[-1].args[0]
    update_values = dict(update_statement.compile().params)
    assert update_values['status'] == 'ai_resumed'
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
uv run pytest tests/unit_tests/api/service/test_sales_service.py::test_send_operator_message_from_session_does_not_create_handoff_when_ai_hosted tests/unit_tests/api/service/test_sales_service.py::test_reply_handoff_keeps_status_open_so_ai_stays_paused tests/unit_tests/api/service/test_sales_service.py::test_restore_ai_hosting_closes_open_handoff -q
```

Expected: failures for missing methods and current `reply_handoff` setting status to `handled`.

- [ ] **Step 3: Add upset-customer handoff keywords**

In `SalesService.classify_intent`, update the `rules` list so the handoff rule includes escalation terms:

```python
            (
                'handoff',
                [
                    '转人工',
                    '人工',
                    '真人',
                    '销售联系',
                    '电话联系',
                    '加微信',
                    '报价单',
                    '合同',
                    '投诉',
                    '生气',
                    '太差',
                    '骗人',
                    '退钱',
                    '不满意',
                    '别废话',
                    '找负责人',
                ],
                0.9,
                True,
            ),
```

- [ ] **Step 4: Implement send and restore helpers**

Add these methods inside `SalesService` near the handoff methods:

```python
    async def send_operator_message_from_session(
        self,
        session_id: str,
        reply: str,
        assigned_to: str = '',
        pause_ai: bool = False,
    ) -> dict[str, Any]:
        session_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringSession).where(
                persistence_monitoring.MonitoringSession.session_id == session_id
            )
        )
        session = self._first_row(session_result)
        if session is None:
            raise ValueError('Session not found')

        handoff_id: int | None = None
        if pause_ai:
            handoff = await self.open_handoff_from_session(session_id, '人工接入处理中', assigned_to)
            handoff_id = int(handoff['id']) if handoff.get('id') else None

        target_type, target_id = self._target_from_session(session)
        await self._send_operator_message(
            bot_uuid=getattr(session, 'bot_id', '') or '',
            target_type=target_type,
            target_id=target_id,
            reply=reply,
        )
        await self._record_operator_monitoring_message(session, reply, assigned_to)
        return {'sent': True, 'handoff_id': handoff_id}

    async def _send_operator_message(self, bot_uuid: str, target_type: str, target_id: str, reply: str) -> None:
        if not bot_uuid or not target_id:
            raise ValueError('Handoff target is missing; cannot send manual reply')
        from langbot_plugin.api.entities.builtin.platform import message as platform_message

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None:
            raise ValueError(f'Bot {bot_uuid} is not running; cannot send manual reply')
        await runtime_bot.adapter.send_message(
            target_type,
            target_id,
            platform_message.MessageChain([platform_message.Plain(text=reply)]),
        )

    async def _record_operator_monitoring_message(self, session: Any, reply: str, assigned_to: str) -> None:
        monitoring_service = getattr(self.ap, 'monitoring_service', None)
        if monitoring_service is None:
            return
        message_content = json.dumps([{'type': 'Plain', 'text': reply}], ensure_ascii=False)
        variables = json.dumps({'sales_sender_kind': 'operator'}, ensure_ascii=False)
        await monitoring_service.record_message(
            bot_id=getattr(session, 'bot_id', '') or '',
            bot_name=getattr(session, 'bot_name', '') or '',
            pipeline_id=getattr(session, 'pipeline_id', '') or '',
            pipeline_name=getattr(session, 'pipeline_name', '') or '',
            message_content=message_content,
            session_id=getattr(session, 'session_id', '') or '',
            status='success',
            level='info',
            platform=getattr(session, 'platform', None),
            user_id=getattr(session, 'user_id', None),
            user_name=getattr(session, 'user_name', None),
            runner_name=assigned_to or '人工销售',
            variables=variables,
            role='assistant',
        )

    async def restore_ai_hosting_from_session(self, session_id: str, assigned_to: str = '') -> dict[str, Any]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.session_id == session_id)
            .where(persistence_sales.SalesHandoff.status == 'open')
        )
        handoff = self._first_row(result)
        if handoff is None:
            return {'restored': True, 'handoff_id': None}
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.id == handoff.id)
            .values(status='ai_resumed', assigned_to=assigned_to or handoff.assigned_to, updated_at=datetime.datetime.now())
        )
        return {'restored': True, 'handoff_id': handoff.id}
```

- [ ] **Step 5: Update `reply_handoff` to keep the handoff open**

Replace the send/update body of `reply_handoff` after the handoff validation with:

```python
        await self._send_operator_message(
            bot_uuid=handoff.bot_uuid,
            target_type=handoff.target_type,
            target_id=handoff.target_id,
            reply=reply,
        )
        session_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_monitoring.MonitoringSession).where(
                persistence_monitoring.MonitoringSession.session_id == handoff.session_id
            )
        )
        session = self._first_row(session_result)
        if session is not None:
            await self._record_operator_monitoring_message(session, reply, assigned_to)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_sales.SalesHandoff)
            .where(persistence_sales.SalesHandoff.id == handoff_id)
            .values(status='open', operator_reply=reply, assigned_to=assigned_to, updated_at=datetime.datetime.now())
        )
```

- [ ] **Step 6: Update `reply_handoff_from_session` to pause AI**

Replace its call to `open_handoff_from_session`/`reply_handoff` with:

```python
        handoff = await self.open_handoff_from_session(session_id, '人工直接回复', assigned_to)
        handoff_id = handoff.get('id')
        if not handoff_id:
            raise ValueError('Handoff id is missing; cannot send manual reply')
        await self.reply_handoff(int(handoff_id), reply, assigned_to)
        return {'sent': True, 'handoff_id': int(handoff_id)}
```

This keeps behavior compatible with existing route names while preserving `status='open'`.

- [ ] **Step 7: Run the tests and verify they pass**

Run:

```powershell
uv run pytest tests/unit_tests/api/service/test_sales_service.py::test_send_operator_message_from_session_does_not_create_handoff_when_ai_hosted tests/unit_tests/api/service/test_sales_service.py::test_reply_handoff_keeps_status_open_so_ai_stays_paused tests/unit_tests/api/service/test_sales_service.py::test_restore_ai_hosting_closes_open_handoff tests/unit_tests/api/service/test_sales_service.py::test_prepare_query_keeps_existing_open_handoff_in_manual_mode -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add tests/unit_tests/api/service/test_sales_service.py src/langbot/pkg/api/http/service/sales.py
git commit -m "feat: control sales chat manual handoff state"
```

---

### Task 4: Add Sales Conversation HTTP Endpoints

**Files:**
- Modify: `tests/integration/api/test_sales.py`
- Modify: `src/langbot/pkg/api/http/controller/groups/sales.py`

- [ ] **Step 1: Write failing endpoint tests**

In `tests/integration/api/test_sales.py`, extend the `fake_sales_app` fixture setup with these mocks:

```python
    app.sales_service.get_sales_conversations = AsyncMock(
        return_value=[
            {
                'session_id': 'person_customer-1',
                'customer_name': '客户A',
                'latest_message_preview': '真实消息',
                'handoff_status': 'ai_hosted',
            }
        ]
    )
    app.sales_service.get_sales_conversation_messages = AsyncMock(
        return_value={'messages': [{'id': 'msg-1', 'preview': '真实消息'}], 'total': 1}
    )
    app.sales_service.send_operator_message_from_session = AsyncMock(return_value={'sent': True, 'handoff_id': None})
    app.sales_service.restore_ai_hosting_from_session = AsyncMock(return_value={'restored': True, 'handoff_id': 7})
```

Add these tests inside `TestSalesHandoffEndpoint`:

```python
    @pytest.mark.asyncio
    async def test_get_sales_conversations_success(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.get(
            '/api/v1/sales/conversations?status=ai_hosted',
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['data']['conversations'][0]['latest_message_preview'] == '真实消息'
        fake_sales_app.sales_service.get_sales_conversations.assert_awaited_with(status='ai_hosted', limit=100, offset=0)

    @pytest.mark.asyncio
    async def test_get_sales_conversation_messages_success(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.get(
            '/api/v1/sales/conversations/person_customer-1/messages',
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['data']['messages'][0]['preview'] == '真实消息'
        fake_sales_app.sales_service.get_sales_conversation_messages.assert_awaited_with(
            'person_customer-1',
            limit=200,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_normal_manual_reply_does_not_request_ai_pause(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.post(
            '/api/v1/sales/conversations/person_customer-1/manual-reply',
            json={'reply': '人工补充', 'assigned_to': 'sales-admin'},
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        fake_sales_app.sales_service.send_operator_message_from_session.assert_awaited_once_with(
            'person_customer-1',
            '人工补充',
            'sales-admin',
            pause_ai=False,
        )

    @pytest.mark.asyncio
    async def test_restore_ai_hosting_endpoint_success(self, quart_test_client, fake_sales_app):
        response = await quart_test_client.post(
            '/api/v1/sales/conversations/person_customer-1/handoff/restore',
            json={'assigned_to': 'sales-admin'},
            headers={'Authorization': 'Bearer test_token'},
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['data']['restored'] is True
        fake_sales_app.sales_service.restore_ai_hosting_from_session.assert_awaited_once_with(
            'person_customer-1',
            'sales-admin',
        )
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
uv run pytest tests/integration/api/test_sales.py::TestSalesHandoffEndpoint::test_get_sales_conversations_success tests/integration/api/test_sales.py::TestSalesHandoffEndpoint::test_get_sales_conversation_messages_success tests/integration/api/test_sales.py::TestSalesHandoffEndpoint::test_normal_manual_reply_does_not_request_ai_pause tests/integration/api/test_sales.py::TestSalesHandoffEndpoint::test_restore_ai_hosting_endpoint_success -q
```

Expected: 404 route failures.

- [ ] **Step 3: Add controller routes**

In `src/langbot/pkg/api/http/controller/groups/sales.py`, add these routes after `/assist/pitch` and before `/memories`:

```python
        @self.route('/conversations', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            status = quart.request.args.get('status')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))
            conversations = await self.ap.sales_service.get_sales_conversations(
                status=status,
                limit=limit,
                offset=offset,
            )
            return self.success(data={'conversations': conversations, 'limit': limit, 'offset': offset})

        @self.route('/conversations/<path:session_id>/messages', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            limit = int(quart.request.args.get('limit', 200))
            offset = int(quart.request.args.get('offset', 0))
            result = await self.ap.sales_service.get_sales_conversation_messages(
                session_id,
                limit=limit,
                offset=offset,
            )
            return self.success(data={**result, 'limit': limit, 'offset': offset})

        @self.route('/conversations/<path:session_id>/manual-reply', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            reply = data.get('reply', '').strip()
            if not reply:
                return self.http_status(400, -1, 'reply is required')
            result = await self.ap.sales_service.send_operator_message_from_session(
                session_id,
                reply,
                data.get('assigned_to', ''),
                pause_ai=False,
            )
            return self.success(data=result)

        @self.route('/conversations/<path:session_id>/handoff/start', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            handoff = await self.ap.sales_service.open_handoff_from_session(
                session_id,
                data.get('reason', '人工主动介入'),
                data.get('assigned_to', ''),
            )
            return self.success(data={'handoff': handoff})

        @self.route('/conversations/<path:session_id>/handoff/reply', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            reply = data.get('reply', '').strip()
            if not reply:
                return self.http_status(400, -1, 'reply is required')
            result = await self.ap.sales_service.reply_handoff_from_session(
                session_id,
                reply,
                data.get('assigned_to', ''),
            )
            return self.success(data=result)

        @self.route('/conversations/<path:session_id>/handoff/restore', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            result = await self.ap.sales_service.restore_ai_hosting_from_session(
                session_id,
                data.get('assigned_to', ''),
            )
            return self.success(data=result)
```

- [ ] **Step 4: Add AI suggestion route**

Add this route after the handoff routes:

```python
        @self.route('/conversations/<path:session_id>/ai-suggestion', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(session_id: str) -> str:
            data = await quart.request.json
            suggestion = await self.ap.sales_service.generate_sales_reply_suggestion_from_session(
                session_id,
                product_uuid=data.get('product_uuid', ''),
                tone=data.get('tone', 'consultative'),
            )
            return self.success(data=suggestion)
```

Then implement the matching service method in `sales.py`:

```python
    async def generate_sales_reply_suggestion_from_session(
        self,
        session_id: str,
        product_uuid: str = '',
        tone: str = 'consultative',
    ) -> dict[str, Any]:
        messages = await self.get_sales_conversation_messages(session_id, limit=20, offset=0)
        context = '\n'.join(message['preview'] for message in messages['messages'][-8:] if message.get('preview'))
        products = await self.get_products(enabled_only=True)
        product = next((item for item in products if item.get('uuid') == product_uuid), None) if product_uuid else None
        if product is None:
            product = self.select_best_product(context, products)
        if product is None:
            raise ValueError('No product available')
        pitch = self.generate_pitch(product, customer_profile=context, intent=context, tone=tone)
        return {'suggestion': pitch, 'product': product}
```

- [ ] **Step 5: Run endpoint tests**

Run:

```powershell
uv run pytest tests/integration/api/test_sales.py::TestSalesHandoffEndpoint -q
```

Expected: all tests in the class pass.

- [ ] **Step 6: Commit**

```powershell
git add tests/integration/api/test_sales.py src/langbot/pkg/api/http/controller/groups/sales.py src/langbot/pkg/api/http/service/sales.py
git commit -m "feat: expose sales conversation endpoints"
```

---

### Task 5: Add Frontend API Types And Client Methods

**Files:**
- Modify: `web/src/app/infra/entities/api/index.ts`
- Modify: `web/src/app/infra/http/BackendClient.ts`

- [ ] **Step 1: Add normalized API types**

In `web/src/app/infra/entities/api/index.ts`, add these interfaces after `SalesHandoff`:

```ts
export type SalesConversationStatus =
  | 'ai_hosted'
  | 'pending_manual'
  | 'manual_handling';

export type SalesMessageComponent =
  | {
      kind: 'text';
      text: string;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'image';
      url?: string;
      base64?: string;
      path?: string;
      name?: string;
      available: boolean;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'voice';
      url?: string;
      base64?: string;
      path?: string;
      length?: number;
      available: boolean;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'file';
      name: string;
      url?: string;
      path?: string;
      available: boolean;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'link';
      title: string;
      description?: string;
      url: string;
      thumb_url?: string;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'quote';
      text: string;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'attachment';
      type: string;
      label: string;
      raw?: Record<string, unknown>;
    };

export interface SalesConversationMessage {
  id: string;
  timestamp: string;
  session_id: string;
  role: string | null;
  sender_kind: 'customer' | 'assistant' | 'operator';
  sender_label: string;
  bot_id: string;
  bot_name: string;
  platform: string | null;
  user_id: string | null;
  user_name: string | null;
  runner_name: string | null;
  status: string;
  level: string;
  preview: string;
  components: SalesMessageComponent[];
  metadata: Record<string, unknown>;
  raw_message_content: string;
}

export interface SalesConversation {
  session_id: string;
  customer_name: string;
  platform: string;
  user_id: string;
  user_name: string;
  bot_id: string;
  bot_name: string;
  message_count: number;
  last_activity: string;
  latest_message: SalesConversationMessage | null;
  latest_message_preview: string;
  handoff_status: SalesConversationStatus;
  handoff: SalesHandoff | null;
  memory: SalesCustomerMemory | null;
}

export interface SalesReplySuggestionResp {
  suggestion: {
    tone: string;
    message: string;
    next_action: string;
  };
  product: SalesProduct;
}
```

- [ ] **Step 2: Import the new types in `BackendClient.ts`**

Add these names to the existing import list from `@/app/infra/entities/api`:

```ts
  SalesConversation,
  SalesConversationMessage,
  SalesConversationStatus,
  SalesReplySuggestionResp,
```

- [ ] **Step 3: Add client methods**

In `BackendClient.ts`, near the existing sales methods, add:

```ts
  public getSalesConversations(params?: {
    status?: SalesConversationStatus | 'all';
    limit?: number;
    offset?: number;
  }): Promise<{
    conversations: SalesConversation[];
    limit: number;
    offset: number;
  }> {
    return this.get('/api/v1/sales/conversations', params);
  }

  public getSalesConversationMessages(
    sessionId: string,
    limit: number = 200,
    offset: number = 0,
  ): Promise<{
    messages: SalesConversationMessage[];
    total: number;
    limit: number;
    offset: number;
  }> {
    return this.get(
      `/api/v1/sales/conversations/${encodeURIComponent(sessionId)}/messages`,
      { limit, offset },
    );
  }

  public sendSalesConversationManualReply(
    sessionId: string,
    reply: string,
    assignedTo?: string,
  ): Promise<{ sent: boolean; handoff_id: number | null }> {
    return this.post(
      `/api/v1/sales/conversations/${encodeURIComponent(sessionId)}/manual-reply`,
      { reply, assigned_to: assignedTo || '' },
    );
  }

  public startSalesConversationHandoff(
    sessionId: string,
    reason?: string,
    assignedTo?: string,
  ): Promise<{ handoff: SalesHandoff }> {
    return this.post(
      `/api/v1/sales/conversations/${encodeURIComponent(sessionId)}/handoff/start`,
      { reason: reason || '人工主动介入', assigned_to: assignedTo || '' },
    );
  }

  public replySalesConversationHandoff(
    sessionId: string,
    reply: string,
    assignedTo?: string,
  ): Promise<{ sent: boolean; handoff_id: number }> {
    return this.post(
      `/api/v1/sales/conversations/${encodeURIComponent(sessionId)}/handoff/reply`,
      { reply, assigned_to: assignedTo || '' },
    );
  }

  public restoreSalesConversationAiHosting(
    sessionId: string,
    assignedTo?: string,
  ): Promise<{ restored: boolean; handoff_id: number | null }> {
    return this.post(
      `/api/v1/sales/conversations/${encodeURIComponent(sessionId)}/handoff/restore`,
      { assigned_to: assignedTo || '' },
    );
  }

  public generateSalesConversationReplySuggestion(
    sessionId: string,
    data?: { product_uuid?: string; tone?: string },
  ): Promise<SalesReplySuggestionResp> {
    return this.post(
      `/api/v1/sales/conversations/${encodeURIComponent(sessionId)}/ai-suggestion`,
      data || {},
    );
  }
```

- [ ] **Step 4: Build TypeScript**

Run:

```powershell
corepack.cmd pnpm --dir web build
```

Expected: TypeScript accepts the new exported types and `BackendClient` methods.

- [ ] **Step 5: Commit**

```powershell
git add web/src/app/infra/entities/api/index.ts web/src/app/infra/http/BackendClient.ts
git commit -m "feat: add sales conversation frontend api"
```

---

### Task 6: Add Frontend Message Component Renderer

**Files:**
- Create: `web/src/app/home/sales-chat/message-components.tsx`

- [ ] **Step 1: Create the renderer component file**

Create `web/src/app/home/sales-chat/message-components.tsx` with:

```tsx
import type { ReactNode } from 'react';
import { FileText, ImageIcon, Link2, Volume2 } from 'lucide-react';

import { SalesMessageComponent } from '@/app/infra/entities/api';
import { cn } from '@/lib/utils';

function mediaSource(component: {
  url?: string;
  base64?: string;
  path?: string;
}): string {
  return component.url || component.base64 || component.path || '';
}

export function SalesMessageComponents({
  components,
  compact = false,
}: {
  components: SalesMessageComponent[];
  compact?: boolean;
}) {
  if (!components.length) {
    return <span className="text-[#8a93a5]">[空消息]</span>;
  }

  return (
    <div className="space-y-2">
      {components.map((component, index) => (
        <SalesMessageComponentView
          key={`${component.kind}-${index}`}
          component={component}
          compact={compact}
        />
      ))}
    </div>
  );
}

function SalesMessageComponentView({
  component,
  compact,
}: {
  component: SalesMessageComponent;
  compact: boolean;
}) {
  if (component.kind === 'text') {
    return <div className="whitespace-pre-wrap break-words">{component.text}</div>;
  }

  if (component.kind === 'image') {
    const src = mediaSource(component);
    if (component.available && src) {
      return (
        <a href={src} target="_blank" rel="noreferrer" className="block">
          <img
            src={src}
            alt={component.name || '聊天图片'}
            className={cn(
              'max-w-full rounded-md border border-black/5 object-cover',
              compact ? 'max-h-20' : 'max-h-72',
            )}
          />
        </a>
      );
    }
    return (
      <AttachmentCard
        icon={<ImageIcon className="size-4" />}
        title="图片"
        detail={component.name || String(component.raw?.image_id || component.raw?.file_id || '图片资源不可直接预览')}
      />
    );
  }

  if (component.kind === 'voice') {
    const src = mediaSource(component);
    if (component.available && src) {
      return (
        <div className="min-w-[220px] rounded-md bg-black/5 px-3 py-2">
          <div className="mb-2 flex items-center gap-2 text-sm">
            <Volume2 className="size-4" />
            <span>{component.length ? `${component.length}s` : '语音消息'}</span>
          </div>
          <audio controls src={src} className="h-9 w-full" />
        </div>
      );
    }
    return (
      <AttachmentCard
        icon={<Volume2 className="size-4" />}
        title="语音"
        detail={String(component.raw?.voice_id || component.raw?.file_id || component.raw?.duration || '语音资源不可直接播放')}
      />
    );
  }

  if (component.kind === 'file') {
    const src = mediaSource(component);
    const card = (
      <AttachmentCard
        icon={<FileText className="size-4" />}
        title={component.name || '文件'}
        detail={component.available ? '点击打开文件' : '文件资源不可直接打开'}
      />
    );
    return component.available && src ? (
      <a href={src} target="_blank" rel="noreferrer">
        {card}
      </a>
    ) : (
      card
    );
  }

  if (component.kind === 'link') {
    return (
      <a
        href={component.url || '#'}
        target="_blank"
        rel="noreferrer"
        className="block rounded-md border border-black/10 bg-white/70 p-3 text-inherit"
      >
        <div className="flex items-center gap-2 font-medium">
          <Link2 className="size-4" />
          <span>{component.title || '链接'}</span>
        </div>
        {component.description && (
          <div className="mt-1 line-clamp-2 text-sm opacity-80">
            {component.description}
          </div>
        )}
        {component.url && (
          <div className="mt-2 truncate text-xs opacity-70">{component.url}</div>
        )}
      </a>
    );
  }

  if (component.kind === 'quote') {
    return (
      <blockquote className="border-l-2 border-black/20 pl-3 text-sm opacity-80">
        {component.text || '引用消息'}
      </blockquote>
    );
  }

  return (
    <AttachmentCard
      icon={<FileText className="size-4" />}
      title={component.label || component.type || '附件'}
      detail={component.type || '未知消息组件'}
    />
  );
}

function AttachmentCard({
  icon,
  title,
  detail,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <div className="flex min-w-[180px] items-center gap-3 rounded-md border border-black/10 bg-white/70 px-3 py-2">
      <div className="flex size-8 items-center justify-center rounded-md bg-black/5">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{title}</div>
        <div className="truncate text-xs opacity-70">{detail}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run TypeScript build**

Run:

```powershell
corepack.cmd pnpm --dir web build
```

Expected: no errors from `message-components.tsx`.

- [ ] **Step 3: Commit**

```powershell
git add web/src/app/home/sales-chat/message-components.tsx
git commit -m "feat: render sales chat media components"
```

---

### Task 7: Rewire 聚合聊天 Page To Normalized Conversations

**Files:**
- Modify: `web/src/app/home/sales-chat/page.tsx`

- [ ] **Step 1: Replace monitoring-message local types with normalized imports**

Update imports from `@/app/infra/entities/api` to include:

```ts
  SalesConversation,
  SalesConversationMessage,
  SalesConversationStatus,
```

Add:

```ts
import { SalesMessageComponents } from './message-components';
```

Remove the local `MonitoringSession`, `MonitoringMessage`, and `ConversationRow` types after all usages have been migrated.

- [ ] **Step 2: Add conversation tab constants**

Add these constants near the other label maps:

```ts
const conversationTabs: Array<{
  value: 'all' | SalesConversationStatus;
  label: string;
}> = [
  { value: 'all', label: '全部' },
  { value: 'ai_hosted', label: 'AI 托管中' },
  { value: 'pending_manual', label: '待人工介入' },
  { value: 'manual_handling', label: '人工处理中' },
];

const handoffStatusLabels: Record<SalesConversationStatus, string> = {
  ai_hosted: 'AI 托管中',
  pending_manual: '待人工介入',
  manual_handling: '人工处理中',
};
```

- [ ] **Step 3: Replace dashboard conversation state**

Replace:

```ts
  const [handoffs, setHandoffs] = useState<SalesHandoff[]>([]);
  const [sessions, setSessions] = useState<MonitoringSession[]>([]);
  const [messages, setMessages] = useState<MonitoringMessage[]>([]);
```

with:

```ts
  const [handoffs, setHandoffs] = useState<SalesHandoff[]>([]);
  const [conversations, setConversations] = useState<SalesConversation[]>([]);
  const [messages, setMessages] = useState<SalesConversationMessage[]>([]);
  const [activeConversationTab, setActiveConversationTab] = useState<
    'all' | SalesConversationStatus
  >('all');
```

Remove the `useMemo(() => buildConversations(...))` block after the new API load is in place.

- [ ] **Step 4: Load normalized conversations**

Inside `loadDashboard`, keep overview/products/memories/handoffs/outreach loading, but replace the monitoring data call with `getSalesConversations`:

```ts
      const [
        overviewData,
        productResp,
        memoryResp,
        handoffResp,
        outreachResp,
        conversationResp,
      ] = await Promise.all([
        httpClient.getSalesOverview(),
        httpClient.getSalesProducts(),
        httpClient.getSalesMemories(),
        httpClient.getSalesHandoffs('open'),
        httpClient.getSalesOutreachPlans(),
        httpClient.getSalesConversations({
          status: activeConversationTab,
          limit: 100,
          offset: 0,
        }),
      ]);
      setOverview(overviewData);
      setProducts(productResp.products || []);
      setMemories(memoryResp.memories || []);
      setHandoffs(handoffResp.handoffs || []);
      setOutreachPlans(outreachResp.plans || []);
      setConversations(conversationResp.conversations || []);
```

Add `activeConversationTab` to the `useCallback` dependency array.

- [ ] **Step 5: Load normalized messages**

Replace `getSessionMessages` usage in `loadMessages` with:

```ts
      const resp = await httpClient.getSalesConversationMessages(
        sessionId,
        200,
        0,
      );
      setMessages(resp.messages || []);
```

Do not sort in the frontend; the backend returns timestamp order.

- [ ] **Step 6: Update send actions**

Replace `sendReply` with this status-aware version:

```ts
  const sendReply = async () => {
    if (!selectedConversation || !draft.trim()) return;
    setSending(true);
    try {
      const reply = draft.trim();
      if (selectedConversation.handoff_status === 'ai_hosted') {
        await httpClient.sendSalesConversationManualReply(
          selectedConversation.session_id,
          reply,
          currentUser,
        );
      } else {
        await httpClient.replySalesConversationHandoff(
          selectedConversation.session_id,
          reply,
          currentUser,
        );
      }
      setDraft('');
      await Promise.all([
        loadDashboard(false),
        loadMessages(selectedConversation.session_id),
      ]);
      toast.success('消息已发送');
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSending(false);
    }
  };
```

Replace `openHandoff` with:

```ts
  const openHandoff = async () => {
    if (!selectedConversation) return;
    try {
      await httpClient.startSalesConversationHandoff(
        selectedConversation.session_id,
        '人工主动介入',
        currentUser,
      );
      await loadDashboard(false);
      toast.success('已进入人工处理中');
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
```

Add:

```ts
  const restoreAiHosting = async () => {
    if (!selectedConversation) return;
    try {
      await httpClient.restoreSalesConversationAiHosting(
        selectedConversation.session_id,
        currentUser,
      );
      await loadDashboard(false);
      toast.success('已恢复 AI 托管');
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  const generateSuggestedReply = async () => {
    if (!selectedConversation) return;
    try {
      const response = await httpClient.generateSalesConversationReplySuggestion(
        selectedConversation.session_id,
      );
      setDraft(response.suggestion.message);
      toast.success('AI 推荐回复已填入草稿');
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
```

- [ ] **Step 7: Update conversation list props and rendering**

Change `ConversationList` to receive:

```ts
  activeTab,
  onTab,
```

with types:

```ts
  activeTab: 'all' | SalesConversationStatus;
  onTab: (value: 'all' | SalesConversationStatus) => void;
```

Render tabs above search:

```tsx
        <div className="grid grid-cols-4 gap-1 rounded-lg bg-[#f2f4f8] p-1">
          {conversationTabs.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => onTab(tab.value)}
              className={cn(
                'rounded-md px-2 py-2 text-sm font-medium text-[#697287]',
                activeTab === tab.value && 'bg-white text-[#1f2a44] shadow-sm',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
```

For each row use normalized fields:

```tsx
conversation.customer_name || conversation.user_name || conversation.user_id || conversation.session_id
conversation.latest_message_preview || '暂无真实消息'
handoffStatusLabels[conversation.handoff_status]
conversation.session_id
conversation.last_activity
```

- [ ] **Step 8: Update chat bubbles to render components**

In `ChatCenter`, replace bubble content:

```tsx
{message.message_content}
```

with:

```tsx
<SalesMessageComponents components={message.components} />
```

Set alignment:

```ts
const isAgent = message.sender_kind === 'assistant' || message.sender_kind === 'operator';
```

Set labels:

```tsx
{message.sender_kind === 'operator'
  ? '人工销售'
  : message.sender_kind === 'assistant'
    ? '数字员工'
    : message.sender_label}
```

- [ ] **Step 9: Add composer controls**

In `ChatCenter` props add:

```ts
  onRestoreAi: () => void;
  onSuggestReply: () => void;
```

Render buttons above the textarea:

```tsx
          <button
            type="button"
            onClick={onSuggestReply}
            disabled={!conversation}
            className="rounded-lg border border-[#dde2ec] px-3 py-2 text-sm text-[#34415c] disabled:opacity-50"
          >
            AI 推荐回复
          </button>
          {conversation?.handoff_status === 'ai_hosted' ? (
            <button
              type="button"
              onClick={onOpenHandoff}
              disabled={!conversation}
              className="rounded-lg border border-[#5f58ff] px-3 py-2 text-sm text-[#5f58ff] disabled:opacity-50"
            >
              接入人工
            </button>
          ) : (
            <button
              type="button"
              onClick={onRestoreAi}
              disabled={!conversation}
              className="rounded-lg border border-emerald-300 px-3 py-2 text-sm text-emerald-700 disabled:opacity-50"
            >
              恢复 AI 托管
            </button>
          )}
```

Keep the send button always available when a conversation and draft exist. The send method decides whether it is a normal manual message or handoff reply.

- [ ] **Step 10: Build frontend**

Run:

```powershell
corepack.cmd pnpm --dir web build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 11: Commit**

```powershell
git add web/src/app/home/sales-chat/page.tsx
git commit -m "feat: rewire sales chat scrm workspace"
```

---

### Task 8: End-To-End Verification With Built-In Database

**Files:**
- No source edits expected.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
uv run pytest tests/unit_tests/api/service/test_sales_service.py tests/integration/api/test_sales.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
corepack.cmd pnpm --dir web build
```

Expected: build passes.

- [ ] **Step 3: Restart backend using built-in database**

Stop any old `python main.py` process for this workspace, then run:

```powershell
$env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe main.py
```

Expected: backend starts and logs the WebUI address, with no database reset.

- [ ] **Step 4: Verify API reads real message rows**

In another shell, run:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5300/api/v1/sales/conversations?limit=5" -Headers @{ Authorization = "Bearer test_token" }
```

If the server requires a real token, use the browser session instead and verify through UI. Expected data shape includes `conversations[*].latest_message_preview` from real messages and no customer summary as transcript preview.

- [ ] **Step 5: Verify page behavior manually**

Open:

```text
http://127.0.0.1:5300/
```

Check:

- 聚合聊天 opens as a workspace.
- 左侧 tabs include 全部, AI 托管中, 待人工介入, 人工处理中.
- The existing built-in database conversation shows real user and AI messages in timestamp order.
- Text bubbles no longer display raw JSON.
- Existing voice rows render as voice cards or playable audio.
- Existing image rows render as image cards or previews.
- In AI 托管中, sending a manual message does not move the session into 待人工介入.
- In 待人工介入/人工处理中, AI remains paused until 恢复 AI 托管.
- AI 推荐回复 fills the draft and does not auto-send.

- [ ] **Step 6: Final status**

Run:

```powershell
git status --short
```

Expected: only intended implementation changes are present. Runtime logs and `.codex-runtime/` remain uncommitted unless the user explicitly asks to manage them.
