from __future__ import annotations

import base64
import gzip
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import escape

import aiohttp
import websockets

DEFAULT_DASHSCOPE_TTS_URL = (
    'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
)
DASHSCOPE_TTS_PATH = '/services/aigc/multimodal-generation/generation'


def resolve_dashscope_tts_url(base_url: str = '') -> str:
    normalized = (base_url or DEFAULT_DASHSCOPE_TTS_URL).strip().rstrip('/')
    if 'multimodal-generation/generation' in normalized:
        return normalized
    if normalized.endswith('/api/v1'):
        return f'{normalized}{DASHSCOPE_TTS_PATH}'
    return normalized or DEFAULT_DASHSCOPE_TTS_URL
DEFAULT_VOLCENGINE_TTS_HTTP_URL = 'https://openspeech.bytedance.com/api/v1/tts'
DEFAULT_VOLCENGINE_TTS_WS_URL = 'wss://openspeech.bytedance.com/api/v1/tts/ws_binary'

_DASHSCOPE_PROVIDERS = frozenset({'dashscope', 'dashscope-tts', 'bailian-tts', 'qwen-tts', 'qwen'})
_VOLCENGINE_PROVIDERS = frozenset({'volcengine', 'doubao', 'volcark', 'bytedance'})
_ELEVENLABS_MODEL_MAP = {
    'multilingual_v2': 'eleven_multilingual_v2',
    'flash_v2_5': 'eleven_flash_v2_5',
    'flash_v2': 'eleven_flash_v2',
}


@dataclass
class TTSInvokeConfig:
    requester: str = ''
    provider: str = ''
    model: str = ''
    text: str = ''
    token: str = ''
    app_id: str = ''
    base_url: str = ''
    voice: str = ''
    voice_type: str = ''
    voice_id: str = ''
    encoding: str = ''
    cluster: str = 'volcano_tts'
    language_type: str = 'Chinese'
    instructions: str | None = None
    optimize_instructions: bool | None = None
    timeout: int = 60
    extra_args: dict[str, Any] = field(default_factory=dict)


def detect_tts_backend(config: TTSInvokeConfig) -> str:
    requester = str(config.requester or '').lower()
    provider = str(config.provider or '').lower()
    base_url = str(config.base_url or '').lower()
    model = str(config.model or '').lower()

    if requester == 'azure-tts' or provider == 'azure':
        return 'azure'
    if requester == 'volcengine-tts' or provider in _VOLCENGINE_PROVIDERS:
        return 'volcengine'
    if requester == 'elevenlabs-tts' or provider == 'elevenlabs':
        return 'elevenlabs'
    if (
        requester in {'bailian-chat-completions', 'dashscope-tts'}
        or provider in _DASHSCOPE_PROVIDERS
        or 'multimodal-generation/generation' in base_url
        or model.startswith('qwen3-tts')
        or model == 'qwen-tts'
    ):
        return 'dashscope'
    if requester == 'zhipuai-chat-completions' or provider in {'zhipu', 'glm'} or model == 'glm-tts':
        return 'zhipu'
    if provider == 'minimax' or 'minimax' in base_url:
        return 'minimax'
    if requester == 'openai-chat-completions' or provider == 'openai':
        if model.startswith('tts') or model.startswith('gpt-4o-mini-tts') or 'tts' in model:
            return 'openai'
    if model.startswith('tts') or model.startswith('gpt-4o-mini-tts') or model.startswith('speech-'):
        if 'minimax' in base_url:
            return 'minimax'
        if provider in _DASHSCOPE_PROVIDERS or model.startswith('qwen'):
            return 'dashscope'
        if provider in _VOLCENGINE_PROVIDERS:
            return 'volcengine'
        return 'openai'
    return 'volcengine'


def apply_provider_api_keys(
    voice_config: dict[str, Any],
    *,
    requester: str,
    api_keys: list[str] | None,
) -> dict[str, Any]:
    resolved = dict(voice_config)
    keys = [str(key).strip() for key in (api_keys or []) if str(key).strip()]
    requester_name = str(requester or '').lower()

    if requester_name == 'volcengine-tts' and len(keys) >= 2:
        if not resolved.get('app_id'):
            resolved['app_id'] = keys[0]
        if not resolved.get('token'):
            resolved['token'] = keys[1]
        return resolved

    if not resolved.get('token') and keys:
        resolved['token'] = keys[0]
    return resolved


def build_tts_invoke_config(voice_config: dict[str, Any], text: str) -> TTSInvokeConfig:
    extra_args = voice_config.get('extra_args') if isinstance(voice_config.get('extra_args'), dict) else {}
    voice = str(voice_config.get('voice') or extra_args.get('voice') or '')
    voice_type = str(voice_config.get('voice_type') or extra_args.get('voice_type') or '')
    voice_id = str(voice_config.get('voice_id') or extra_args.get('voice_id') or voice or voice_type or '')

    return TTSInvokeConfig(
        requester=str(voice_config.get('requester') or ''),
        provider=str(voice_config.get('provider') or extra_args.get('provider') or ''),
        model=str(voice_config.get('model') or ''),
        text=text,
        token=str(voice_config.get('token') or ''),
        app_id=str(voice_config.get('app_id') or ''),
        base_url=str(voice_config.get('base_url') or ''),
        voice=voice,
        voice_type=voice_type,
        voice_id=voice_id,
        encoding=str(voice_config.get('encoding') or ''),
        cluster=str(voice_config.get('cluster') or extra_args.get('cluster') or 'volcano_tts'),
        language_type=str(voice_config.get('language_type') or extra_args.get('language_type') or 'Chinese'),
        instructions=voice_config.get('instructions') or extra_args.get('instructions'),
        optimize_instructions=voice_config.get('optimize_instructions', extra_args.get('optimize_instructions')),
        extra_args=extra_args,
    )


def apply_env_fallbacks(config: TTSInvokeConfig) -> TTSInvokeConfig:
    backend = detect_tts_backend(config)
    token = config.token
    app_id = config.app_id

    if backend == 'dashscope' and not token:
        token = os.getenv('DASHSCOPE_API_KEY', '')
    elif backend == 'openai' and not token:
        token = os.getenv('OPENAI_API_KEY', '') or os.getenv('DASHSCOPE_API_KEY', '')
    elif backend == 'azure' and not token:
        token = os.getenv('AZURE_TTS_KEY', '') or os.getenv('AZURE_SPEECH_KEY', '')
    elif backend == 'elevenlabs' and not token:
        token = os.getenv('ELEVENLABS_API_KEY', '')
    elif backend == 'minimax' and not token:
        token = os.getenv('MINIMAX_API_KEY', '')
    elif backend == 'zhipu' and not token:
        token = os.getenv('ZHIPUAI_API_KEY', '') or os.getenv('GLM_API_KEY', '')

    if backend == 'volcengine':
        if not app_id:
            app_id = (
                os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_APP_ID')
                or os.getenv('VOLCENGINE_TTS_APP_ID')
                or ''
            )
        if not token:
            token = (
                os.getenv('LANGBOT_TASK_ASSISTANT_VOLC_TTS_TOKEN')
                or os.getenv('VOLCENGINE_TTS_TOKEN')
                or ''
            )

    return TTSInvokeConfig(
        requester=config.requester,
        provider=config.provider,
        model=config.model,
        text=config.text,
        token=token,
        app_id=app_id,
        base_url=config.base_url,
        voice=config.voice,
        voice_type=config.voice_type,
        voice_id=config.voice_id,
        encoding=config.encoding,
        cluster=config.cluster,
        language_type=config.language_type,
        instructions=config.instructions,
        optimize_instructions=config.optimize_instructions,
        timeout=config.timeout,
        extra_args=config.extra_args,
    )


def default_encoding_for_backend(config: TTSInvokeConfig) -> str:
    if config.encoding:
        return config.encoding
    backend = detect_tts_backend(config)
    if backend in {'dashscope', 'zhipu'}:
        return 'wav'
    if backend == 'volcengine':
        return 'ogg_opus'
    return 'mp3'


def tts_mime_type(encoding: str) -> str:
    if encoding == 'ogg_opus':
        return 'audio/ogg'
    if encoding == 'wav':
        return 'audio/wav'
    return 'audio/mpeg'


async def invoke_tts(config: TTSInvokeConfig, logger: logging.Logger | None = None) -> str | None:
    config = apply_env_fallbacks(config)
    if not config.encoding:
        config = TTSInvokeConfig(
            **{**config.__dict__, 'encoding': default_encoding_for_backend(config)}
        )

    backend = detect_tts_backend(config)
    dispatch = {
        'azure': _request_azure_tts,
        'volcengine': _request_volcengine_tts,
        'elevenlabs': _request_elevenlabs_tts,
        'dashscope': _request_dashscope_tts,
        'zhipu': _request_zhipu_tts,
        'minimax': _request_minimax_tts,
        'openai': _request_openai_tts,
    }
    handler = dispatch.get(backend, _request_volcengine_tts)
    return await handler(config, logger)


async def _request_openai_tts(config: TTSInvokeConfig, logger: logging.Logger | None) -> str | None:
    if not config.token:
        _log_warning(logger, 'OpenAI TTS skipped: api key is not configured')
        return None

    base_url = (config.base_url or 'https://api.openai.com/v1').rstrip('/')
    url = f'{base_url}/audio/speech'
    response_format = _openai_response_format(config.encoding)
    payload = {
        'model': config.model or 'tts-1',
        'input': config.text,
        'voice': config.voice or config.voice_type or 'alloy',
        'response_format': response_format,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {config.token}',
                'Content-Type': 'application/json',
            },
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as response:
            if response.status != 200:
                body = await response.text()
                _log_warning(
                    logger,
                    'OpenAI TTS request failed: status=%s body=%s',
                    response.status,
                    body[:200],
                )
                return None
            audio_bytes = await response.read()
    return base64.b64encode(audio_bytes).decode('utf-8')


async def _request_azure_tts(config: TTSInvokeConfig, logger: logging.Logger | None) -> str | None:
    if not config.token:
        _log_warning(logger, 'Azure TTS skipped: api key is not configured')
        return None

    base_url = (config.base_url or 'https://eastus.tts.speech.microsoft.com').rstrip('/')
    url = f'{base_url}/cognitiveservices/v1'
    voice_name = config.voice or config.voice_type or 'zh-CN-XiaoxiaoNeural'
    ssml = (
        "<speak version='1.0' xml:lang='zh-CN'>"
        f"<voice name='{escape(voice_name)}'>{escape(config.text)}</voice>"
        '</speak>'
    )
    headers = {
        'Ocp-Apim-Subscription-Key': config.token,
        'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': _azure_output_format(config.encoding),
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=ssml.encode('utf-8'),
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as response:
            if response.status != 200:
                body = await response.text()
                _log_warning(
                    logger,
                    'Azure TTS request failed: status=%s body=%s',
                    response.status,
                    body[:200],
                )
                return None
            audio_bytes = await response.read()
    return base64.b64encode(audio_bytes).decode('utf-8')


async def _request_zhipu_tts(config: TTSInvokeConfig, logger: logging.Logger | None) -> str | None:
    if not config.token:
        _log_warning(logger, 'GLM TTS skipped: api key is not configured')
        return None

    base_url = (config.base_url or 'https://open.bigmodel.cn/api/paas/v4').rstrip('/')
    url = f'{base_url}/audio/speech'
    payload = {
        'model': config.model or 'glm-tts',
        'input': config.text,
        'voice': config.voice or config.voice_type or 'female',
        'response_format': 'wav' if config.encoding == 'wav' else 'mp3',
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {config.token}',
                'Content-Type': 'application/json',
            },
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as response:
            if response.status != 200:
                body = await response.text()
                _log_warning(
                    logger,
                    'GLM TTS request failed: status=%s body=%s',
                    response.status,
                    body[:200],
                )
                return None
            audio_bytes = await response.read()
    return base64.b64encode(audio_bytes).decode('utf-8')


async def _request_minimax_tts(config: TTSInvokeConfig, logger: logging.Logger | None) -> str | None:
    if not config.token:
        _log_warning(logger, 'MiniMax TTS skipped: api key is not configured')
        return None

    base_url = (config.base_url or 'https://api.minimaxi.com').rstrip('/')
    url = f'{base_url}/v1/t2a_v2'
    audio_format = 'wav' if config.encoding == 'wav' else 'mp3'
    payload = {
        'model': config.model or 'speech-2.8-hd',
        'text': config.text,
        'stream': False,
        'output_format': 'hex',
        'voice_setting': {
            'voice_id': config.voice_id or config.voice or config.voice_type or 'female-shaonv',
            'speed': 1,
            'vol': 1,
            'pitch': 0,
        },
        'audio_setting': {
            'sample_rate': 32000,
            'bitrate': 128000,
            'format': audio_format,
            'channel': 1,
        },
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {config.token}',
                'Content-Type': 'application/json',
            },
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as response:
            data = await response.json(content_type=None)

    base_resp = data.get('base_resp') if isinstance(data, dict) else None
    status_code = base_resp.get('status_code') if isinstance(base_resp, dict) else None
    if response.status != 200 or (status_code not in (None, 0)):
        _log_warning(
            logger,
            'MiniMax TTS request failed: status=%s code=%s message=%s',
            response.status,
            status_code,
            base_resp.get('status_msg') if isinstance(base_resp, dict) else data,
        )
        return None

    audio_hex = ((data.get('data') or {}).get('audio') if isinstance(data, dict) else None) or ''
    if not audio_hex:
        _log_warning(logger, 'MiniMax TTS response did not include audio data')
        return None
    return base64.b64encode(bytes.fromhex(audio_hex)).decode('utf-8')


async def _request_elevenlabs_tts(config: TTSInvokeConfig, logger: logging.Logger | None) -> str | None:
    if not config.token:
        _log_warning(logger, 'ElevenLabs TTS skipped: api key is not configured')
        return None

    base_url = (config.base_url or 'https://api.elevenlabs.io/v1').rstrip('/')
    voice_id = config.voice_id or config.voice or config.voice_type or 'JBFqnCBsd6RMkjVDRZzb'
    model_id = _ELEVENLABS_MODEL_MAP.get(config.model, config.model or 'eleven_multilingual_v2')
    url = f'{base_url}/text-to-speech/{voice_id}'
    payload = {
        'text': config.text,
        'model_id': model_id,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers={
                'xi-api-key': config.token,
                'Content-Type': 'application/json',
                'Accept': 'audio/mpeg',
            },
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as response:
            if response.status != 200:
                body = await response.text()
                _log_warning(
                    logger,
                    'ElevenLabs TTS request failed: status=%s body=%s',
                    response.status,
                    body[:200],
                )
                return None
            audio_bytes = await response.read()
    return base64.b64encode(audio_bytes).decode('utf-8')


async def _request_dashscope_tts(config: TTSInvokeConfig, logger: logging.Logger | None) -> str | None:
    if not config.token:
        _log_warning(logger, 'DashScope TTS skipped: api key is not configured')
        return None

    url = resolve_dashscope_tts_url(config.base_url)
    input_payload: dict[str, Any] = {
        'text': config.text,
        'voice': config.voice or config.voice_type or 'Cherry',
        'language_type': config.language_type,
    }
    if config.instructions:
        input_payload['instructions'] = config.instructions
    if config.optimize_instructions is not None:
        input_payload['optimize_instructions'] = bool(config.optimize_instructions)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={'model': config.model or 'qwen3-tts-flash', 'input': input_payload},
            headers={
                'Authorization': f'Bearer {config.token}',
                'Content-Type': 'application/json',
            },
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as response:
            data = await response.json(content_type=None)

        if response.status != 200 or data.get('status_code') not in (None, 200):
            _log_warning(
                logger,
                'DashScope TTS request failed: status=%s code=%s message=%s',
                response.status,
                data.get('code'),
                data.get('message'),
            )
            return None

        audio = data.get('output', {}).get('audio', {})
        audio_base64 = audio.get('data')
        if audio_base64:
            return audio_base64

        audio_url = audio.get('url')
        if not audio_url:
            _log_warning(logger, 'DashScope TTS response did not include audio data or url')
            return None

        async with session.get(
            audio_url,
            timeout=aiohttp.ClientTimeout(total=config.timeout),
        ) as audio_response:
            if audio_response.status != 200:
                _log_warning(
                    logger,
                    'DashScope TTS audio download failed: status=%s',
                    audio_response.status,
                )
                return None
            audio_bytes = await audio_response.read()
    return base64.b64encode(audio_bytes).decode('utf-8')


async def _request_volcengine_tts(config: TTSInvokeConfig, logger: logging.Logger | None) -> str | None:
    if not config.app_id or not config.token:
        _log_warning(logger, 'Volcengine TTS skipped: app_id/token is not configured')
        return None

    voice_type = config.voice_type or config.voice or 'zh_female_yuanqinvyou_moon_bigtts'
    encoding = config.encoding or 'ogg_opus'
    if voice_type.endswith('_bigtts') or encoding == 'ogg_opus':
        audio_base64 = await _request_volcengine_tts_ws(
            text=config.text,
            app_id=config.app_id,
            token=config.token,
            cluster=config.cluster,
            voice_type=voice_type,
            encoding=encoding,
            logger=logger,
        )
        if audio_base64:
            return audio_base64

    payload = {
        'app': {
            'appid': config.app_id,
            'token': config.token,
            'cluster': config.cluster,
        },
        'user': {'uid': 'langbot-task-assistant'},
        'audio': {
            'voice_type': voice_type,
            'encoding': encoding,
            'speed_ratio': 1.0,
            'volume_ratio': 1.0,
            'pitch_ratio': 1.0,
        },
        'request': {
            'reqid': str(uuid.uuid4()),
            'text': config.text,
            'text_type': 'plain',
            'operation': 'query',
        },
    }
    http_url = _volcengine_http_url(config.base_url)
    for authorization in (f'Bearer;{config.token}', f'Bearer {config.token}'):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                http_url,
                json=payload,
                headers={'Authorization': authorization},
                timeout=aiohttp.ClientTimeout(total=config.timeout),
            ) as response:
                data = await response.json(content_type=None)
        if response.status == 200 and data.get('code') == 3000 and data.get('data'):
            return data['data']
        _log_warning(
            logger,
            'Volcengine TTS request failed: status=%s code=%s message=%s',
            response.status,
            data.get('code'),
            data.get('message'),
        )
    return None


async def _request_volcengine_tts_ws(
    *,
    text: str,
    app_id: str,
    token: str,
    cluster: str,
    voice_type: str,
    encoding: str,
    logger: logging.Logger | None,
    base_url: str = '',
) -> str | None:
    payload = {
        'app': {
            'appid': app_id,
            'token': token,
            'cluster': cluster,
        },
        'user': {'uid': 'langbot-task-assistant'},
        'audio': {
            'voice_type': voice_type,
            'encoding': encoding,
            'speed_ratio': 1.0,
            'volume_ratio': 1.0,
            'pitch_ratio': 1.0,
        },
        'request': {
            'reqid': str(uuid.uuid4()),
            'text': text,
            'text_type': 'plain',
            'operation': 'submit',
        },
    }
    body = gzip.compress(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
    request_bytes = bytes([0x11, 0x10, 0x11, 0x00]) + len(body).to_bytes(4, 'big') + body
    ws_url = _volcengine_ws_url(base_url)

    for authorization in (f'Bearer;{token}', f'Bearer; {token}'):
        audio_chunks: list[bytes] = []
        try:
            async with websockets.connect(
                ws_url,
                additional_headers={'Authorization': authorization},
                open_timeout=10,
                close_timeout=5,
                max_size=None,
            ) as websocket:
                await websocket.send(request_bytes)
                async for message in websocket:
                    if isinstance(message, str):
                        continue
                    audio_chunk, is_final = parse_volcengine_tts_ws_audio_message(message)
                    if audio_chunk:
                        audio_chunks.append(audio_chunk)
                    if is_final:
                        break
            if audio_chunks:
                return base64.b64encode(b''.join(audio_chunks)).decode('utf-8')
        except Exception as exc:
            _log_warning(logger, 'Volcengine TTS websocket request failed: %s', exc)
    return None


def parse_volcengine_tts_ws_audio_message(message: bytes) -> tuple[bytes, bool]:
    if len(message) < 4:
        raise ValueError('Volcengine TTS websocket response is too short')

    header_size = (message[0] & 0x0F) * 4
    message_type = (message[1] & 0xF0) >> 4
    message_flags = message[1] & 0x0F
    compression = message[2] & 0x0F
    payload = message[header_size:]

    if message_type == 0xB:
        if message_flags == 0:
            return b'', False
        if len(payload) < 8:
            raise ValueError('Volcengine TTS websocket audio payload is too short')
        sequence_number = int.from_bytes(payload[:4], 'big', signed=True)
        payload_size = int.from_bytes(payload[4:8], 'big', signed=False)
        return payload[8 : 8 + payload_size], sequence_number < 0

    if message_type == 0xF:
        if len(payload) < 8:
            raise ValueError('Volcengine TTS websocket error payload is too short')
        error_code = int.from_bytes(payload[:4], 'big', signed=False)
        error_size = int.from_bytes(payload[4:8], 'big', signed=False)
        error_payload = payload[8 : 8 + error_size]
        if compression == 1:
            error_payload = gzip.decompress(error_payload)
        error_message = error_payload.decode('utf-8', errors='replace')
        raise ValueError(f'Volcengine TTS websocket error {error_code}: {error_message}')

    return b'', False


def _openai_response_format(encoding: str) -> str:
    if encoding in {'ogg_opus', 'opus'}:
        return 'opus'
    if encoding == 'wav':
        return 'wav'
    return 'mp3'


def _azure_output_format(encoding: str) -> str:
    if encoding == 'wav':
        return 'riff-16khz-16bit-mono-pcm'
    if encoding in {'ogg_opus', 'opus'}:
        return 'ogg-16khz-16bit-mono-opus'
    return 'audio-16khz-128kbitrate-mono-mp3'


def _volcengine_http_url(base_url: str) -> str:
    normalized = (base_url or '').rstrip('/')
    if not normalized:
        return DEFAULT_VOLCENGINE_TTS_HTTP_URL
    if normalized.endswith('/api/v1/tts'):
        return normalized
    return f'{normalized}/api/v1/tts'


def _volcengine_ws_url(base_url: str) -> str:
    normalized = (base_url or '').rstrip('/')
    if not normalized:
        return DEFAULT_VOLCENGINE_TTS_WS_URL
    if normalized.startswith('https://'):
        normalized = 'wss://' + normalized[len('https://') :]
    elif normalized.startswith('http://'):
        normalized = 'ws://' + normalized[len('http://') :]
    if normalized.endswith('/api/v1/tts/ws_binary'):
        return normalized
    if normalized.endswith('/api/v1/tts'):
        return normalized + '/ws_binary'
    return f'{normalized}/api/v1/tts/ws_binary'


def _log_warning(logger: logging.Logger | None, message: str, *args: Any) -> None:
    if logger is not None:
        logger.warning(message, *args)
