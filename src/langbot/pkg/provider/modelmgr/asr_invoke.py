from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import aiohttp

DEFAULT_DASHSCOPE_ASR_URL = (
    'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
)
DASHSCOPE_ASR_PATH = '/services/aigc/multimodal-generation/generation'
DEFAULT_SAMPLE_AUDIO_URL = 'https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3'
DEFAULT_VOLCENGINE_ASR_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash'
VOLCENGINE_ASR_PATH = '/api/v3/auc/bigmodel/recognize/flash'

_DASHSCOPE_PROVIDERS = frozenset({'dashscope', 'dashscope-asr', 'dashscope-tts', 'bailian-asr', 'qwen-asr', 'qwen'})
_VOLCENGINE_PROVIDERS = frozenset({'volcengine', 'volcengine-asr', 'doubao', 'doubao-asr', 'bytedance-asr'})


@dataclass
class ASRInvokeConfig:
    requester: str = ''
    provider: str = ''
    model: str = ''
    token: str = ''
    base_url: str = ''
    audio_url: str = ''
    audio_base64: str = ''
    language_type: str = 'Chinese'
    extra_args: dict[str, Any] = field(default_factory=dict)


def resolve_dashscope_asr_url(base_url: str = '') -> str:
    normalized = (base_url or DEFAULT_DASHSCOPE_ASR_URL).strip().rstrip('/')
    if 'multimodal-generation/generation' in normalized:
        return normalized
    if normalized.endswith('/api/v1'):
        return f'{normalized}{DASHSCOPE_ASR_PATH}'
    return normalized or DEFAULT_DASHSCOPE_ASR_URL


def resolve_volcengine_asr_url(base_url: str = '') -> str:
    normalized = (base_url or 'https://openspeech.bytedance.com').strip().rstrip('/')
    if normalized.endswith('/recognize/flash'):
        return normalized
    if normalized.endswith('/api/v3/auc/bigmodel'):
        return f'{normalized}/recognize/flash'
    return f'{normalized}{VOLCENGINE_ASR_PATH}'


def apply_provider_api_keys(
    asr_config: dict[str, Any],
    *,
    requester: str,
    api_keys: list[str] | None,
) -> dict[str, Any]:
    resolved = dict(asr_config)
    keys = [str(key).strip() for key in (api_keys or []) if str(key).strip()]
    if not resolved.get('token') and keys:
        resolved['token'] = keys[0]
    if requester and not resolved.get('requester'):
        resolved['requester'] = requester
    return resolved


def build_asr_invoke_config(asr_config: dict[str, Any]) -> ASRInvokeConfig:
    extra_args = asr_config.get('extra_args') if isinstance(asr_config.get('extra_args'), dict) else {}
    return ASRInvokeConfig(
        requester=str(asr_config.get('requester') or ''),
        provider=str(asr_config.get('provider') or extra_args.get('provider') or ''),
        model=str(asr_config.get('model') or asr_config.get('name') or ''),
        token=str(asr_config.get('token') or ''),
        base_url=str(asr_config.get('base_url') or ''),
        audio_url=str(asr_config.get('audio_url') or extra_args.get('audio_url') or ''),
        audio_base64=str(asr_config.get('audio_base64') or asr_config.get('test_audio_base64') or ''),
        language_type=str(asr_config.get('language_type') or extra_args.get('language_type') or 'Chinese'),
        extra_args=extra_args,
    )


def _log_warning(logger: logging.Logger | None, message: str, *args: Any) -> None:
    if logger is not None:
        logger.warning(message, *args)


def _resolve_audio_source(config: ASRInvokeConfig) -> str:
    if config.audio_base64:
        payload = config.audio_base64.strip()
        if payload.startswith('data:'):
            return payload
        return f'data:audio/webm;base64,{payload}'
    if config.audio_url:
        return config.audio_url
    return DEFAULT_SAMPLE_AUDIO_URL


def _resolve_volcengine_audio(config: ASRInvokeConfig) -> dict[str, str]:
    if config.audio_base64:
        payload = config.audio_base64.strip()
        if payload.startswith('data:') and ',' in payload:
            payload = payload.split(',', 1)[1]
        return {'data': payload}
    if config.audio_url:
        return {'url': config.audio_url}
    return {'url': DEFAULT_SAMPLE_AUDIO_URL}


def _extract_recognition_text(data: dict[str, Any]) -> str:
    result = data.get('result') if isinstance(data.get('result'), dict) else {}
    text = result.get('text') if isinstance(result, dict) else ''
    if isinstance(text, str) and text.strip():
        return text.strip()
    utterances = result.get('utterances') if isinstance(result, dict) else None
    if isinstance(utterances, list):
        parts = [
            str(item.get('text') or '').strip()
            for item in utterances
            if isinstance(item, dict) and str(item.get('text') or '').strip()
        ]
        if parts:
            return ''.join(parts)

    output = data.get('output') if isinstance(data.get('output'), dict) else {}
    choices = output.get('choices')
    if isinstance(choices, list) and choices:
        message = choices[0].get('message') if isinstance(choices[0], dict) else {}
        content = message.get('content') if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get('text')
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return '\n'.join(parts)
    text = output.get('text')
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ''


async def _request_volcengine_asr(config: ASRInvokeConfig, logger: logging.Logger | None) -> str | None:
    if not config.token:
        _log_warning(logger, 'Volcengine ASR skipped: api key is not configured')
        return None

    payload = {
        'user': {'uid': str(config.extra_args.get('uid') or uuid.uuid4())},
        'audio': {**_resolve_volcengine_audio(config), 'format': str(config.extra_args.get('format') or '')},
        'request': {
            'model_name': config.model or 'bigmodel',
            'enable_itn': bool(config.extra_args.get('enable_itn', True)),
            'enable_punc': bool(config.extra_args.get('enable_punc', True)),
            'language': config.language_type or 'zh-CN',
        },
    }
    if not payload['audio']['format']:
        payload['audio'].pop('format')

    async with aiohttp.ClientSession() as session:
        async with session.post(
            resolve_volcengine_asr_url(config.base_url),
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Api-Key': config.token,
                'X-Api-Resource-Id': str(config.extra_args.get('resource_id') or 'volc.bigasr.auc_turbo'),
                'X-Api-Request-Id': str(uuid.uuid4()),
                'X-Api-Sequence': '-1',
            },
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            data = await response.json(content_type=None)

    if response.status != 200:
        _log_warning(logger, 'Volcengine ASR request failed: status=%s response=%s', response.status, data)
        return None

    text = _extract_recognition_text(data if isinstance(data, dict) else {})
    if not text:
        _log_warning(logger, 'Volcengine ASR response did not include recognition text')
        return None
    return text


async def _request_dashscope_asr(config: ASRInvokeConfig, logger: logging.Logger | None) -> str | None:
    if not config.token:
        _log_warning(logger, 'DashScope ASR skipped: api key is not configured')
        return None

    url = resolve_dashscope_asr_url(config.base_url)
    audio = _resolve_audio_source(config)
    payload = {
        'model': config.model or 'qwen3-asr-flash',
        'input': {
            'messages': [
                {'role': 'system', 'content': [{'text': ''}]},
                {'role': 'user', 'content': [{'audio': audio}]},
            ],
        },
        'parameters': {
            'asr_options': {
                'enable_itn': bool(config.extra_args.get('enable_itn', False)),
            },
        },
    }
    if config.language_type:
        payload['parameters']['asr_options']['language'] = config.language_type

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {config.token}',
                'Content-Type': 'application/json',
            },
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            data = await response.json(content_type=None)

    if response.status != 200 or data.get('code') not in (None, '', 200):
        _log_warning(
            logger,
            'DashScope ASR request failed: status=%s code=%s message=%s',
            response.status,
            data.get('code'),
            data.get('message'),
        )
        return None

    text = _extract_recognition_text(data if isinstance(data, dict) else {})
    if not text:
        _log_warning(logger, 'DashScope ASR response did not include recognition text')
        return None
    return text


async def invoke_asr(config: ASRInvokeConfig, logger: logging.Logger | None = None) -> str | None:
    provider = (config.provider or config.requester or '').lower()
    if provider in _DASHSCOPE_PROVIDERS or 'dashscope' in (config.base_url or ''):
        return await _request_dashscope_asr(config, logger)
    if provider in _VOLCENGINE_PROVIDERS or 'openspeech.bytedance.com' in (config.base_url or ''):
        return await _request_volcengine_asr(config, logger)
    _log_warning(logger, 'Unsupported ASR provider: %s', provider or config.requester)
    return None
