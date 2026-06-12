import pytest

from langbot.pkg.provider.modelmgr import audio_content
from langbot_plugin.api.entities.builtin.platform import message as platform_message


def test_infer_voice_filename_from_data_uri():
    voice = platform_message.Voice(
        base64='data:audio/mpeg;base64,abc123',
    )
    assert audio_content.infer_voice_filename(voice) == 'voice.mp3'


def test_model_supports_native_audio_for_gemini():
    assert audio_content.model_supports_native_audio(
        abilities=['vision', 'func_call'],
        requester='geminichatcmpl',
        model_name='gemini-3-flash-preview',
    )


def test_model_supports_native_audio_for_gemini_compatible_proxy():
    assert audio_content.model_supports_native_audio(
        abilities=['vision', 'func_call'],
        requester='openai-chat-completions',
        model_name='gemini-3-flash-preview',
    )


def test_model_supports_native_audio_requires_known_requester_without_audio_ability():
    assert not audio_content.model_supports_native_audio(
        abilities=['func_call'],
        requester='unknownchatcmpl',
        model_name='text-model',
    )


@pytest.mark.asyncio
async def test_transform_message_part_for_gemini_input_audio():
    part = {
        'type': 'file_base64',
        'file_base64': 'data:audio/mpeg;base64,YWJj',
        'file_name': 'voice.mp3',
    }
    transformed = await audio_content.transform_message_part_for_gemini_input_audio(part)
    assert transformed is True
    assert part['type'] == 'input_audio'
    assert part['input_audio']['format'] == 'mp3'
    assert part['input_audio']['data'] == 'YWJj'
