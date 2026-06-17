import json
from types import SimpleNamespace

import pytest

from langbot.pkg.api.http.service.monitoring import MonitoringService


class _CapturePersistence:
    def __init__(self) -> None:
        self.inserted_values = None

    async def execute_async(self, statement):
        compiled = statement.compile()
        self.inserted_values = dict(compiled.params)


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
