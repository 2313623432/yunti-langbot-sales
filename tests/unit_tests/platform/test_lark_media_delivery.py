import pytest
import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.pkg.platform.sources.lark import LarkMessageConverter


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
