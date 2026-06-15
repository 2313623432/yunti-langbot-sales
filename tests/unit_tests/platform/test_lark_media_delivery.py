import pytest
from types import SimpleNamespace
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events

from langbot.pkg.platform.sources.lark import LarkAdapter, LarkEventConverter, LarkMessageConverter


def test_lark_base64_image_decoder_accepts_data_uri_whitespace_and_missing_padding():
    payload = 'data:image/png;base64, aGVs\nbG8'

    image_bytes, mime_type = LarkMessageConverter._decode_base64_media_data(payload)

    assert image_bytes == b'hello'
    assert mime_type == 'image/png'


def test_lark_voice_upload_options_use_audio_message_for_ogg_opus_data_uri():
    voice_options = LarkMessageConverter._voice_upload_options('data:audio/ogg;base64,ZmFrZQ==')

    assert voice_options == {'file_type': 'opus', 'file_name': 'voice.opus'}


@pytest.mark.asyncio
async def test_lark_voice_delivery_passes_duration_for_opus_audio(monkeypatch):
    captured_upload = {}

    async def fake_upload_file_to_lark(file_bytes, api_client, file_type, file_name='file', duration=None):
        captured_upload.update(
            {
                'file_bytes': file_bytes,
                'file_type': file_type,
                'file_name': file_name,
                'duration': duration,
            }
        )
        return 'file-key'

    monkeypatch.setattr(
        LarkMessageConverter,
        'upload_file_to_lark',
        staticmethod(fake_upload_file_to_lark),
    )
    message_chain = platform_message.MessageChain(
        [platform_message.Voice(base64='data:audio/ogg;base64,ZmFrZQ==', length=4)]
    )

    text_elements, media_items = await LarkMessageConverter.yiri2target(message_chain, api_client=None)

    assert text_elements == []
    assert media_items == [{'msg_type': 'audio', 'content': {'file_key': 'file-key'}}]
    assert captured_upload == {
        'file_bytes': b'fake',
        'file_type': 'opus',
        'file_name': 'voice.opus',
        'duration': 4000,
    }


@pytest.mark.asyncio
async def test_lark_contact_added_event_reads_nested_operator_id():
    captured = {}

    async def callback(contact_info):
        captured.update(contact_info)

    adapter = LarkAdapter.model_construct(contact_added_callback=callback)

    await adapter._handle_contact_added_event(
        {
            'event_type': 'im.chat.access_event.bot_p2p_chat_entered_v1',
            'operator': {
                'operator_id': {
                    'open_id': 'ou_new_customer',
                    'user_id': 'user_new_customer',
                }
            }
        }
    )

    assert captured == {
        'user_id': 'ou_new_customer',
        'platform': 'lark',
        'event_type': 'im.chat.access_event.bot_p2p_chat_entered_v1',
    }


def test_lark_contact_added_uses_first_created_or_entered_events():
    assert LarkAdapter._is_contact_added_chat_access_event('im.chat.access_event.bot_p2p_chat_created_v1') is True
    assert LarkAdapter._is_contact_added_chat_access_event('im.chat.access_event.bot_p2p_chat_entered_v1') is True
    assert LarkAdapter._is_contact_added_chat_access_event('im.message.receive_v1') is False


@pytest.mark.asyncio
async def test_lark_friend_message_uses_contact_display_name():
    class FakeUserClient:
        async def aget(self, request):
            assert request.user_id == 'ou_customer'
            return SimpleNamespace(
                success=lambda: True,
                data=SimpleNamespace(user=SimpleNamespace(name='张三', nickname='小张')),
            )

    api_client = SimpleNamespace(contact=SimpleNamespace(v3=SimpleNamespace(user=FakeUserClient())))
    event = SimpleNamespace(
        event=SimpleNamespace(
            sender=SimpleNamespace(
                sender_id=SimpleNamespace(open_id='ou_customer', union_id='on_technical_identifier_123456')
            ),
            message=SimpleNamespace(
                message_id='om_message',
                message_type='text',
                content='{"text":"你好"}',
                create_time='1710000000000',
                mentions=[],
                chat_type='p2p',
                chat_id='oc_chat',
                parent_id=None,
                thread_id=None,
            ),
        )
    )

    converted = await LarkEventConverter.target2yiri(event, api_client)

    assert isinstance(converted, platform_events.FriendMessage)
    assert converted.sender.id == 'ou_customer'
    assert converted.sender.nickname == '张三'


@pytest.mark.asyncio
async def test_lark_friend_message_uses_sender_display_name_when_contact_lookup_fails():
    class FakeUserClient:
        async def aget(self, request):
            return SimpleNamespace(success=lambda: False, code=403, msg='forbidden')

    api_client = SimpleNamespace(contact=SimpleNamespace(v3=SimpleNamespace(user=FakeUserClient())))
    event = SimpleNamespace(
        event=SimpleNamespace(
            sender=SimpleNamespace(
                sender_id=SimpleNamespace(open_id='ou_customer', union_id='on_technical_identifier_123456'),
                name='Customer Name',
                display_name='Display Name',
            ),
            message=SimpleNamespace(
                message_id='om_message',
                message_type='text',
                content='{"text":"hello"}',
                create_time='1710000000000',
                mentions=[],
                chat_type='p2p',
                chat_id='oc_chat',
                parent_id=None,
                thread_id=None,
            ),
        )
    )

    converted = await LarkEventConverter.target2yiri(event, api_client)

    assert isinstance(converted, platform_events.FriendMessage)
    assert converted.sender.nickname == 'Customer Name'
