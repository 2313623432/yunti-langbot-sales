from __future__ import annotations

from importlib import import_module
from unittest.mock import call

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message

from tests.factories import FakeApp, text_query


def get_respback_stage_class():
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.respback.respback').SendResponseBackStage


def _pipeline_config(*, multi_reply_enabled: bool, threshold: int = 20) -> dict:
    return {
        'output': {
            'force-delay': {'min': 0, 'max': 0},
            'misc': {
                'at-sender': False,
                'quote-origin': False,
                'multi-reply': {
                    'enabled': multi_reply_enabled,
                    'threshold': threshold,
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_respback_splits_long_plain_text_when_multi_reply_enabled():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('hello')
    query.pipeline_config = _pipeline_config(multi_reply_enabled=True, threshold=10)
    query.resp_message_chain = [
        platform_message.MessageChain(
            [
                platform_message.Plain(text='第一段内容很长。\n第二段内容也很长。'),
            ]
        )
    ]

    await stage.process(query, 'SendResponseBackStage')

    sent_texts = [
        str(kwargs['message'])
        for _, kwargs in query.adapter.reply_message.await_args_list
    ]
    assert sent_texts == ['第一段内容很长。', '第二段内容也很长。']


@pytest.mark.asyncio
async def test_respback_keeps_plain_text_as_single_message_when_multi_reply_disabled():
    app = FakeApp()
    stage = get_respback_stage_class()(app)
    query = text_query('hello')
    query.pipeline_config = _pipeline_config(multi_reply_enabled=False, threshold=10)
    text = '第一段内容很长。\n第二段内容也很长。'
    query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text=text)])
    ]

    await stage.process(query, 'SendResponseBackStage')

    query.adapter.reply_message.assert_awaited_once()
    assert query.adapter.reply_message.await_args == call(
        message_source=query.message_event,
        message=query.resp_message_chain[-1],
        quote_origin=False,
    )
