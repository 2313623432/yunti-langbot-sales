from langbot.pkg.platform.sources.lark import LarkMessageConverter


def test_lark_base64_image_decoder_accepts_data_uri_whitespace_and_missing_padding():
    payload = 'data:image/png;base64, aGVs\nbG8'

    image_bytes, mime_type = LarkMessageConverter._decode_base64_media_data(payload)

    assert image_bytes == b'hello'
    assert mime_type == 'image/png'


def test_lark_voice_upload_options_use_audio_message_for_ogg_opus_data_uri():
    voice_options = LarkMessageConverter._voice_upload_options('data:audio/ogg;base64,ZmFrZQ==')

    assert voice_options == {'file_type': 'opus', 'file_name': 'voice.opus'}
