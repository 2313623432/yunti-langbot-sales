from unittest.mock import AsyncMock, patch

import pytest

from langbot.pkg.provider.modelmgr import tts_invoke


def test_detect_tts_backend_for_builtin_providers():
    assert (
        tts_invoke.detect_tts_backend(
            tts_invoke.TTSInvokeConfig(requester='azure-tts', model='azure-neural')
        )
        == 'azure'
    )
    assert (
        tts_invoke.detect_tts_backend(
            tts_invoke.TTSInvokeConfig(requester='volcengine-tts', provider='volcengine')
        )
        == 'volcengine'
    )
    assert (
        tts_invoke.detect_tts_backend(
            tts_invoke.TTSInvokeConfig(requester='elevenlabs-tts', model='multilingual_v2')
        )
        == 'elevenlabs'
    )
    assert (
        tts_invoke.detect_tts_backend(
            tts_invoke.TTSInvokeConfig(provider='dashscope-tts', model='qwen3-tts-flash')
        )
        == 'dashscope'
    )
    assert (
        tts_invoke.detect_tts_backend(
            tts_invoke.TTSInvokeConfig(requester='zhipuai-chat-completions', model='glm-tts')
        )
        == 'zhipu'
    )
    assert (
        tts_invoke.detect_tts_backend(
            tts_invoke.TTSInvokeConfig(
                requester='openai-chat-completions',
                provider='openai',
                model='tts-1',
            )
        )
        == 'openai'
    )
    assert (
        tts_invoke.detect_tts_backend(
            tts_invoke.TTSInvokeConfig(
                provider='minimax',
                base_url='https://api.minimaxi.com',
                model='speech-2.8-hd',
            )
        )
        == 'minimax'
    )
    assert (
        tts_invoke.detect_tts_backend(
            tts_invoke.TTSInvokeConfig(
                requester='openai-chat-completions',
                base_url='https://openspeech.bytedance.com',
                model='seed-tts-2.0-standard',
            )
        )
        == 'volcengine'
    )


def test_resolve_dashscope_tts_url_from_api_v1_base():
    assert (
        tts_invoke.resolve_dashscope_tts_url('https://dashscope.aliyuncs.com/api/v1')
        == tts_invoke.DEFAULT_DASHSCOPE_TTS_URL
    )


def test_resolve_dashscope_tts_url_keeps_full_endpoint():
    full_url = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
    assert tts_invoke.resolve_dashscope_tts_url(full_url) == full_url


def test_apply_provider_api_keys_for_volcengine_dual_keys():
    resolved = tts_invoke.apply_provider_api_keys(
        {'model': 'volcano_tts'},
        requester='volcengine-tts',
        api_keys=['app-123', 'token-456'],
    )

    assert resolved['app_id'] == 'app-123'
    assert resolved['token'] == 'token-456'


def test_apply_provider_api_keys_for_volcengine_seed_tts_single_key():
    resolved = tts_invoke.apply_provider_api_keys(
        {'model': 'seed-tts-2.0-standard'},
        requester='openai-chat-completions',
        api_keys=['speech-api-key'],
    )

    assert resolved['token'] == 'speech-api-key'
    assert 'app_id' not in resolved


def test_apply_provider_api_keys_preserves_existing_values():
    resolved = tts_invoke.apply_provider_api_keys(
        {'app_id': 'existing-app', 'token': 'existing-token'},
        requester='volcengine-tts',
        api_keys=['app-123', 'token-456'],
    )

    assert resolved['app_id'] == 'existing-app'
    assert resolved['token'] == 'existing-token'


def test_default_encoding_for_backend():
    assert (
        tts_invoke.default_encoding_for_backend(
            tts_invoke.TTSInvokeConfig(provider='dashscope-tts', model='qwen3-tts-flash')
        )
        == 'wav'
    )
    assert (
        tts_invoke.default_encoding_for_backend(
            tts_invoke.TTSInvokeConfig(requester='volcengine-tts')
        )
        == 'ogg_opus'
    )


def test_parse_volcengine_tts_ws_audio_message_returns_audio_and_final_state():
    audio_bytes = b'fake-audio'
    sequence_number = -1
    message = (
        bytes([0x11, 0xB3, 0x00, 0x00])
        + sequence_number.to_bytes(4, 'big', signed=True)
        + len(audio_bytes).to_bytes(4, 'big')
        + audio_bytes
    )

    chunk, is_final = tts_invoke.parse_volcengine_tts_ws_audio_message(message)

    assert chunk == audio_bytes
    assert is_final is True


def test_parse_volcengine_tts_v3_stream_concatenated_json_audio():
    raw = ''.join(
        [
            '{"code":0,"data":"YXVkaW8t"}',
            '{"code":0,"data":"Ynl0ZXM="}',
            '{"code":20000000,"message":"ok"}',
        ]
    )

    assert tts_invoke.parse_volcengine_tts_v3_stream(raw) == b'audio-bytes'


@pytest.mark.asyncio
async def test_invoke_volcengine_seed_tts_uses_v3_api_key_headers():
    captured = {}

    class _Content:
        async def iter_chunked(self, _size):
            yield b'{"code":0,"data":"YXVkaW8tYnl0ZXM="}'
            yield b'{"code":20000000,"message":"ok"}'

    class _Response:
        status = 200
        content = _Content()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _Session:
        def post(self, url, **kwargs):
            captured['url'] = url
            captured['kwargs'] = kwargs
            return _Response()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    config = tts_invoke.TTSInvokeConfig(
        requester='openai-chat-completions',
        base_url='https://openspeech.bytedance.com',
        model='seed-tts-2.0-standard',
        text='你好',
        token='speech-api-key',
        voice_type='zh_female_vv_uranus_bigtts',
        encoding='mp3',
        extra_args={'resource_id': 'seed-tts-2.0'},
    )
    with patch('langbot.pkg.provider.modelmgr.tts_invoke.aiohttp.ClientSession', return_value=_Session()):
        result = await tts_invoke.invoke_tts(config)

    assert result == 'YXVkaW8tYnl0ZXM='
    assert captured['url'] == 'https://openspeech.bytedance.com/api/v3/tts/unidirectional'
    assert captured['kwargs']['headers']['X-Api-Key'] == 'speech-api-key'
    assert captured['kwargs']['headers']['X-Api-Resource-Id'] == 'seed-tts-2.0'
    assert captured['kwargs']['json']['req_params']['speaker'] == 'zh_female_vv_uranus_bigtts'
    assert captured['kwargs']['json']['req_params']['audio_params']['format'] == 'mp3'


@pytest.mark.asyncio
async def test_invoke_tts_openai_returns_base64_audio():
    config = tts_invoke.TTSInvokeConfig(
        requester='openai-chat-completions',
        provider='openai',
        model='tts-1',
        text='hello',
        token='test-key',
        encoding='mp3',
    )

    class _Response:
        status = 200

        async def read(self):
            return b'audio-bytes'

    class _Context:
        async def __aenter__(self):
            return _Response()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _Session:
        def post(self, *args, **kwargs):
            return _Context()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch('langbot.pkg.provider.modelmgr.tts_invoke.aiohttp.ClientSession', return_value=_Session()):
        result = await tts_invoke.invoke_tts(config)

    assert result == 'YXVkaW8tYnl0ZXM='


@pytest.mark.asyncio
async def test_catalog_requester_invoke_tts_delegates_to_shared_module():
    from langbot.pkg.provider.modelmgr.requesters.catalog_requester import VolcengineTTSRequester

    requester = VolcengineTTSRequester(
        ap=type('App', (), {'logger': None})(),
        config={'base_url': 'https://openspeech.bytedance.com'},
    )

    with patch(
        'langbot.pkg.provider.modelmgr.requesters.catalog_requester.tts_invoke.invoke_tts',
        new=AsyncMock(return_value='ZmFrZQ=='),
    ) as invoke_mock:
        result = await requester.invoke_tts(
            text='hello',
            model_name='volcano_tts',
            api_keys=['app-id', 'token'],
            extra_args={'voice_type': 'zh_female_test_moon_bigtts'},
        )

    assert result == 'ZmFrZQ=='
    invoke_mock.assert_awaited_once()
    config = invoke_mock.await_args.args[0]
    assert config.app_id == 'app-id'
    assert config.token == 'token'
    assert config.voice_type == 'zh_female_test_moon_bigtts'
