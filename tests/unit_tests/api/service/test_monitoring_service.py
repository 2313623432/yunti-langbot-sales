import json
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service.monitoring import MonitoringService


class _CapturePersistence:
    def __init__(self) -> None:
        self.inserted_values = None

    async def execute_async(self, statement):
        compiled = statement.compile()
        self.inserted_values = dict(compiled.params)


class _FakeResult:
    def __init__(self, rows=None, scalar_value=0):
        self._rows = rows or []
        self._scalar_value = scalar_value

    def scalar(self):
        return self._scalar_value

    def all(self):
        return self._rows


class _RowWrapper:
    def __init__(self, value):
        self._value = value

    def __getitem__(self, index):
        if index != 0:
            raise IndexError(index)
        return self._value


class _ColumnRow:
    def __init__(self, **values):
        self._values = values
        self._mapping = values

    def __getitem__(self, index):
        if index != 0:
            raise IndexError(index)
        return self._values['id']


@pytest.mark.asyncio
async def test_record_message_adds_sales_reply_quality_metrics_for_assistant_reply():
    persistence = _CapturePersistence()
    service = MonitoringService(SimpleNamespace(persistence_mgr=persistence))
    message_content = json.dumps(
        [
            {
                'type': 'Plain',
                'text': '作为AI助手，我建议先领取试听课。\n详情：https://example.com/course\n您看这样可以吗？',
            }
        ],
        ensure_ascii=False,
    )

    await service.record_message(
        bot_id='bot-1',
        bot_name='Sales Bot',
        pipeline_id='pipe-1',
        pipeline_name='Sales Pipeline',
        message_content=message_content,
        session_id='session-1',
        variables=json.dumps({'existing': True}, ensure_ascii=False),
        role='assistant',
    )

    variables = json.loads(persistence.inserted_values['variables'])

    assert variables['existing'] is True
    assert variables['sales_reply_quality'] == {
        'text_length': 56,
        'max_line_length': 29,
        'ends_with_question': True,
        'contains_link': True,
        'has_ai_like_phrasing': True,
        'ai_like_markers': ['作为AI助手'],
    }


@pytest.mark.asyncio
async def test_get_messages_returns_compact_media_content_for_lists():
    huge_image = 'data:image/png;base64,' + ('A' * 1_000_000)
    message = SimpleNamespace(
        id='msg-1',
        timestamp=datetime.datetime(2026, 6, 23, 9, 0, 0),
        bot_id='bot-1',
        bot_name='私域机器人1',
        pipeline_id='pipe-1',
        pipeline_name='销售流程',
        message_content=json.dumps(
            [{'type': 'Plain', 'text': '我拍给你看'}, {'type': 'Image', 'base64': huge_image}],
            ensure_ascii=False,
        ),
        session_id='session-1',
        status='success',
        level='info',
        platform='person',
        user_id='ou_customer',
        user_name='夏般',
        runner_name='',
        variables=None,
        role='user',
    )
    persistence = SimpleNamespace(
        execute_async=AsyncMock(
            side_effect=[
                _FakeResult(scalar_value=1),
                _FakeResult(rows=[_ColumnRow(**message.__dict__)]),
            ]
        ),
        serialize_model=lambda model, value: {
            column.name: getattr(value, column.name) for column in model.__table__.columns
        },
    )
    service = MonitoringService(SimpleNamespace(persistence_mgr=persistence))

    messages, total = await service.get_messages(limit=50)

    assert total == 1
    assert len(json.dumps(messages, ensure_ascii=False, default=str)) < 10_000
    assert 'data:image/png;base64' not in messages[0]['message_content']
    assert json.loads(messages[0]['message_content']) == [
        {'type': 'Plain', 'text': '我拍给你看'},
        {'type': 'Image', 'media_omitted': True},
    ]
