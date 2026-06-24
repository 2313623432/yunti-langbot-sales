from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
from langbot.pkg.platform.sources.dingtalk import DingTalkAdapter


def _message_chain(text: str) -> platform_message.MessageChain:
    return platform_message.MessageChain([platform_message.Plain(text=text)])


def _incoming_message() -> SimpleNamespace:
    return SimpleNamespace(
        sender_staff_id='staff-1',
        sender_nick='少华',
        conversation_id='cid-1',
    )


def _friend_event() -> platform_events.FriendMessage:
    return platform_events.FriendMessage(
        type='FriendMessage',
        sender=platform_entities.Friend(id='staff-1', nickname='少华', remark=''),
        message_chain=_message_chain('四年级'),
        time=1609459200,
        source_platform_object=DingTalkEvent({'IncomingMessage': _incoming_message()}),
    )


@pytest.mark.asyncio
async def test_dingtalk_reply_message_without_quote_uses_proactive_person_message():
    bot = SimpleNamespace(
        send_message=AsyncMock(),
        send_proactive_message_to_one=AsyncMock(),
        send_proactive_message_to_group=AsyncMock(),
    )
    adapter = DingTalkAdapter.model_construct(
        config={'markdown_card': False},
        bot=bot,
    )

    await adapter.reply_message(
        message_source=_friend_event(),
        message=_message_chain('主要补拼读规律和单词记忆方法哦'),
        quote_origin=False,
    )

    bot.send_message.assert_not_awaited()
    bot.send_proactive_message_to_one.assert_awaited_once_with(
        'staff-1',
        '主要补拼读规律和单词记忆方法哦',
    )
    bot.send_proactive_message_to_group.assert_not_awaited()


@pytest.mark.asyncio
async def test_dingtalk_reply_message_with_quote_keeps_reply_person_message():
    bot = SimpleNamespace(
        send_message=AsyncMock(),
        send_proactive_message_to_one=AsyncMock(),
        send_proactive_message_to_group=AsyncMock(),
    )
    incoming_message = _incoming_message()
    adapter = DingTalkAdapter.model_construct(
        config={'markdown_card': False},
        bot=bot,
    )
    event = _friend_event()
    event.source_platform_object = DingTalkEvent({'IncomingMessage': incoming_message})

    await adapter.reply_message(
        message_source=event,
        message=_message_chain('咱们这个自然拼读刚好适合四年级孩子'),
        quote_origin=True,
    )

    bot.send_message.assert_awaited_once_with(
        '咱们这个自然拼读刚好适合四年级孩子',
        incoming_message,
        False,
    )
    bot.send_proactive_message_to_one.assert_not_awaited()
    bot.send_proactive_message_to_group.assert_not_awaited()
