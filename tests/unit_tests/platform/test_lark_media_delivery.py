import pytest
import asyncio
import threading
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langbot.pkg.platform.sources.lark import LarkAdapter, LarkEventConverter, LarkMessageConverter
from lark_oapi.core.enum import AccessTokenType, HttpMethod
from lark_oapi.api.im.v1 import EventMessage


@pytest.mark.asyncio
async def test_lark_non_webhook_run_starts_and_cleans_ping_loop():
    class FakeBot:
        def __init__(self):
            self._auto_reconnect = True
            self.connected = False
            self.disconnected = False
            self.ping_started = asyncio.Event()
            self.ping_cancelled = False

        async def _connect(self):
            self.connected = True

        async def _disconnect(self):
            self.disconnected = True

        async def _reconnect(self):
            self.connected = True

        async def _ping_loop(self):
            self.ping_started.set()
            try:
                while True:
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                self.ping_cancelled = True
                raise

    fake_bot = FakeBot()
    adapter = LarkAdapter.model_construct(
        config={'enable-webhook': False},
        bot=fake_bot,
        logger=SimpleNamespace(info=AsyncMock()),
        lark_ping_task=None,
    )

    run_task = asyncio.create_task(adapter.run_async())
    await asyncio.wait_for(fake_bot.ping_started.wait(), timeout=1)

    assert fake_bot.connected is True
    assert adapter.lark_ping_task is not None
    assert adapter.lark_ping_task.done() is False

    run_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run_task

    assert fake_bot.ping_cancelled is True


@pytest.mark.asyncio
async def test_lark_adapter_schedules_sdk_callbacks_on_captured_loop_from_other_thread():
    completed = asyncio.Event()
    adapter = LarkAdapter.model_construct(
        lark_event_loop=asyncio.get_running_loop(),
        logger=SimpleNamespace(error=AsyncMock()),
    )

    async def callback():
        completed.set()

    thread = threading.Thread(target=lambda: adapter._schedule_lark_callback(callback(), 'test callback'))
    thread.start()
    thread.join(timeout=1)

    await asyncio.wait_for(completed.wait(), timeout=1)


def test_lark_base64_image_decoder_accepts_data_uri_whitespace_and_missing_padding():
    payload = 'data:image/png;base64, aGVs\nbG8'

    image_bytes, mime_type = LarkMessageConverter._decode_base64_media_data(payload)

    assert image_bytes == b'hello'
    assert mime_type == 'image/png'


def test_lark_voice_upload_options_use_audio_message_for_ogg_opus_data_uri():
    voice_options = LarkMessageConverter._voice_upload_options('data:audio/ogg;base64,ZmFrZQ==')

    assert voice_options == {'file_type': 'opus', 'file_name': 'voice.opus'}


def test_lark_sticker_file_key_support_requires_shared_message_component():
    assert LarkMessageConverter.supports_lark_sticker_file_key_components() is False
    assert LarkMessageConverter.lark_sticker_file_key_from_component(platform_message.Plain(text='😊')) is None
    assert LarkMessageConverter.lark_sticker_file_key_from_component(
        platform_message.Face(face_type='face', face_id=1, face_name='smile')
    ) is None


@pytest.mark.asyncio
async def test_lark_text_emoji_fallback_remains_plain_post_content():
    message_chain = platform_message.MessageChain([platform_message.Plain(text='😊 家长您好')])

    text_elements, media_items = await LarkMessageConverter.yiri2target(message_chain, api_client=None)

    assert text_elements == [[{'tag': 'md', 'text': '😊 家长您好'}]]
    assert media_items == []


@pytest.mark.asyncio
async def test_lark_adapter_add_message_reaction_uses_feishu_reaction_api():
    captured = {}

    class FakeApiClient:
        async def arequest(self, request, option):
            captured['request'] = request
            captured['option'] = option
            return SimpleNamespace(success=lambda: True, code=0, msg='ok', raw=SimpleNamespace(content=b'{}'))

    adapter = LarkAdapter.model_construct(
        api_client=FakeApiClient(),
        config={'app_type': 'self'},
        app_ticket='ticket',
        get_app_access_token=lambda: 'app-token',
        logger=SimpleNamespace(warning=AsyncMock()),
    )

    sent = await adapter.add_message_reaction('om_user_msg', 'SMILE')

    assert sent is True
    request = captured['request']
    assert request.http_method == HttpMethod.POST
    assert request.uri == '/open-apis/im/v1/messages/om_user_msg/reactions'
    assert request.token_types == {AccessTokenType.TENANT, AccessTokenType.USER}
    assert request.body == {'reaction_type': {'emoji_type': 'SMILE'}}
    assert captured['option'].app_ticket == 'ticket'
    assert captured['option'].app_access_token is None


@pytest.mark.asyncio
async def test_lark_inbound_image_uses_lazy_image_id_without_download():
    class FailingMessageResource:
        async def aget(self, request):
            raise AssertionError('image resources should not be downloaded before aggregation')

    class FakeImV1:
        message_resource = FailingMessageResource()

    class FakeIm:
        v1 = FakeImV1()

    class FakeApiClient:
        im = FakeIm()

    event_message = EventMessage(
        {
            'message_id': 'om_message',
            'message_type': 'image',
            'content': '{"image_key": "img_key"}',
            'create_time': '1781504754000',
            'mentions': [],
        }
    )

    chain = await LarkMessageConverter.target2yiri(event_message, FakeApiClient())

    assert isinstance(chain[1], platform_message.Image)
    assert chain[1].image_id == 'lark:om_message:img_key'
    assert chain[1].base64 == ''


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


@pytest.mark.asyncio
async def test_lark_friend_message_uses_contact_display_name_from_dict_response():
    class FakeUserClient:
        async def aget(self, request):
            assert request.user_id == 'ou_customer'
            return SimpleNamespace(
                success=lambda: True,
                data={'user': {'name': '少华', 'nickname': '少华昵称'}},
            )

    api_client = SimpleNamespace(contact=SimpleNamespace(v3=SimpleNamespace(user=FakeUserClient())))
    event = SimpleNamespace(
        event=SimpleNamespace(
            sender=SimpleNamespace(sender_id=SimpleNamespace(open_id='ou_customer', union_id='on_technical_id_123456')),
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
    assert converted.sender.nickname == '少华'


@pytest.mark.asyncio
async def test_lark_contact_lookup_failure_logs_warning_and_uses_fallback_name():
    class FakeUserClient:
        async def aget(self, request):
            return SimpleNamespace(success=lambda: False, code=99991663, msg='no user authority')

    class FakeLogger:
        def __init__(self):
            self.warnings = []

        async def warning(self, text, images=None, message_session_id=None, no_throw=True):
            self.warnings.append(text)

    api_client = SimpleNamespace(contact=SimpleNamespace(v3=SimpleNamespace(user=FakeUserClient())))
    logger = FakeLogger()

    display_name = await LarkEventConverter._fetch_user_display_name(
        api_client,
        'ou_customer_abcdefghijklmnopqrstuvwxyz',
        '事件显示名',
        logger,
    )

    assert display_name == '事件显示名'
    assert logger.warnings
    assert 'no user authority' in logger.warnings[0]
