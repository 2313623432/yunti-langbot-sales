from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.pipeline.monitoring_helper import MonitoringHelper


@pytest.mark.asyncio
async def test_record_query_start_reuses_raw_monitoring_message_id():
    monitoring_service = SimpleNamespace(
        record_message=AsyncMock(),
        update_session_activity=AsyncMock(),
        record_session_start=AsyncMock(),
    )
    app = SimpleNamespace(monitoring_service=monitoring_service, logger=SimpleNamespace(error=lambda *_: None))
    query = SimpleNamespace(
        variables={'_raw_monitoring_message_ids': ['raw-message-1', 'raw-message-2']},
        launcher_type=SimpleNamespace(value='person'),
        launcher_id='customer-1',
        sender_id='customer-1',
        message_event=SimpleNamespace(sender=SimpleNamespace(nickname='张三')),
        message_chain=[],
    )

    message_id = await MonitoringHelper.record_query_start(
        app,
        query,
        bot_id='bot-uuid',
        bot_name='夏般的智能助手',
        pipeline_id='pipeline-uuid',
        pipeline_name='销售流程',
    )

    assert message_id == 'raw-message-1'
    monitoring_service.record_message.assert_not_awaited()
    monitoring_service.update_session_activity.assert_not_awaited()
