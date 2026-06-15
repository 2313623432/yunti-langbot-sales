from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.pkg.platform.logger import EventLogger


@pytest.mark.asyncio
async def test_event_logger_skips_unavailable_image_bytes():
    storage_provider = SimpleNamespace(save=AsyncMock(), delete=AsyncMock())
    ap = SimpleNamespace(storage_mgr=SimpleNamespace(storage_provider=storage_provider))
    logger = EventLogger(name='test', ap=ap)

    await logger.info('incoming image', images=[platform_message.Image(image_id='lark:om_message:img_key')])

    assert len(logger.logs) == 1
    assert logger.logs[0].text == 'incoming image'
    assert logger.logs[0].images == []
    storage_provider.save.assert_not_called()
