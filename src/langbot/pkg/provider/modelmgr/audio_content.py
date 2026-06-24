from __future__ import annotations

import base64
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

MIME_TO_AUDIO_FORMAT: dict[str, str] = {
    'audio/mpeg': 'mp3',
    'audio/mp3': 'mp3',
    'audio/wav': 'wav',
    'audio/x-wav': 'wav',
    'audio/wave': 'wav',
    'audio/ogg': 'ogg',
    'audio/opus': 'ogg',
    'audio/webm': 'webm',
    'audio/mp4': 'mp4',
    'audio/m4a': 'mp4',
    'audio/x-m4a': 'mp4',
    'audio/flac': 'flac',
    'audio/aac': 'aac',
    'audio/amr': 'amr',
}

EXT_TO_AUDIO_FORMAT: dict[str, str] = {
    'mp3': 'mp3',
    'wav': 'wav',
    'ogg': 'ogg',
    'opus': 'ogg',
    'webm': 'webm',
    'mp4': 'mp4',
    'm4a': 'mp4',
    'flac': 'flac',
    'aac': 'aac',
    'amr': 'amr',
}

UNSUPPORTED_VOICE_FORMATS = frozenset({'silk', 'slk', 'amr'})

DATA_URI_PATTERN = re.compile(r'^data:(?P<mime>[^;]+);base64,(?P<data>.+)$', re.DOTALL)

AUDIO_NATIVE_REQUESTER_HINTS = (
    'geminichatcmpl',
    'bailianchatcmpl',
    'openaichatcmpl',
)


def infer_audio_format_from_mime(mime_type: str) -> str | None:
    normalized = (mime_type or '').split(';')[0].strip().lower()
    if not normalized:
        return None
    if normalized in MIME_TO_AUDIO_FORMAT:
        return MIME_TO_AUDIO_FORMAT[normalized]
    if normalized.startswith('audio/'):
        suffix = normalized.split('/', 1)[1]
        return EXT_TO_AUDIO_FORMAT.get(suffix)
    return None


def infer_audio_format_from_filename(file_name: str) -> str | None:
    normalized = (file_name or '').strip().lower()
    if not normalized or '.' not in normalized:
        return None
    ext = normalized.rsplit('.', 1)[-1]
    return EXT_TO_AUDIO_FORMAT.get(ext)


def parse_data_uri(payload: str) -> tuple[str, str] | None:
    match = DATA_URI_PATTERN.match((payload or '').strip())
    if not match:
        return None
    mime_type = match.group('mime')
    audio_format = infer_audio_format_from_mime(mime_type)
    if not audio_format:
        return None
    return match.group('data'), audio_format


def infer_voice_filename(voice: platform_message.Voice) -> str:
    if voice.base64:
        parsed = parse_data_uri(voice.base64)
        if parsed:
            return f'voice.{parsed[1]}'
    if voice.path:
        path = Path(str(voice.path))
        if path.suffix:
            return f'voice{path.suffix.lower()}'
    if voice.url:
        parsed_url = urlparse(str(voice.url))
        suffix = Path(parsed_url.path).suffix.lower()
        if suffix:
            return f'voice{suffix}'
        if parsed_url.scheme in {'http', 'https'}:
            return 'voice.mp3'
    return 'voice.mp3'


def voice_to_file_content(voice: platform_message.Voice) -> provider_message.ContentElement | None:
    file_name = infer_voice_filename(voice)
    if voice.base64:
        return provider_message.ContentElement.from_file_base64(voice.base64, file_name)
    if voice.url:
        return provider_message.ContentElement.from_file_url(voice.url, file_name)
    if voice.path:
        return provider_message.ContentElement.from_file_url(f'file://{voice.path}', file_name)
    return None


def model_supports_native_audio(
    *,
    abilities: list[str] | None,
    requester: str = '',
    model_name: str = '',
) -> bool:
    normalized_abilities = [str(item) for item in (abilities or [])]
    if 'audio' in normalized_abilities:
        return True

    requester_key = (requester or '').lower()
    requester_compact = re.sub(r'[^a-z0-9]', '', requester_key)
    model_key = (model_name or '').lower()
    if 'gemini' in model_key and 'vision' in normalized_abilities:
        return True
    if any(hint in requester_key or hint in requester_compact for hint in AUDIO_NATIVE_REQUESTER_HINTS):
        if 'vision' in normalized_abilities or 'audio' in normalized_abilities:
            return True
        if 'gemini' in model_key:
            return True

    audio_keywords = ('audio', 'omni', 'multimodal')
    if any(keyword in model_key for keyword in audio_keywords):
        return True

    return False


def _read_local_file_url(file_url: str) -> bytes | None:
    parsed = urlparse(file_url)
    if parsed.scheme != 'file':
        return None
    path = Path(parsed.path)
    if not path.exists():
        return None
    return path.read_bytes()


async def _fetch_remote_audio(file_url: str) -> tuple[bytes, str | None] | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
            if response.status >= 400:
                return None
            content_type = response.headers.get('content-type', '')
            return await response.read(), infer_audio_format_from_mime(content_type)


async def resolve_input_audio_payload(
    *,
    file_url: str = '',
    file_base64: str = '',
    file_name: str = '',
    logger: logging.Logger | None = None,
) -> dict[str, str] | None:
    if file_base64:
        parsed = parse_data_uri(file_base64)
        if parsed:
            return {'data': parsed[0], 'format': parsed[1]}
        audio_format = infer_audio_format_from_filename(file_name) or 'mp3'
        payload = file_base64.strip()
        if payload.startswith('data:'):
            return None
        return {'data': payload, 'format': audio_format}

    if not file_url:
        return None

    audio_format = infer_audio_format_from_filename(file_name)
    if file_url.startswith('file://'):
        raw = _read_local_file_url(file_url)
        if raw is None:
            return None
        if not audio_format:
            audio_format = infer_audio_format_from_filename(file_url) or 'mp3'
        return {'data': base64.b64encode(raw).decode('ascii'), 'format': audio_format}

    parsed_url = urlparse(file_url)
    if parsed_url.scheme in {'http', 'https'}:
        fetched = await _fetch_remote_audio(file_url)
        if fetched is None:
            if logger is not None:
                logger.warning('Failed to fetch remote audio for multimodal input: %s', file_url)
            return None
        raw, remote_format = fetched
        if not audio_format:
            audio_format = remote_format or infer_audio_format_from_filename(file_url) or 'mp3'
        return {'data': base64.b64encode(raw).decode('ascii'), 'format': audio_format}

    return None


async def transform_message_part_for_gemini_input_audio(
    part: dict[str, Any],
    *,
    logger: logging.Logger | None = None,
) -> bool:
    part_type = part.get('type')
    if part_type not in {'file_url', 'file_base64'}:
        return False

    file_name = str(part.get('file_name') or '')
    inferred_format = infer_audio_format_from_filename(file_name)
    if inferred_format in UNSUPPORTED_VOICE_FORMATS:
        return False

    payload = await resolve_input_audio_payload(
        file_url=str(part.get('file_url') or ''),
        file_base64=str(part.get('file_base64') or ''),
        file_name=file_name,
        logger=logger,
    )
    if payload is None:
        return False

    part.clear()
    part.update(
        {
            'type': 'input_audio',
            'input_audio': payload,
        }
    )
    return True


async def transform_messages_for_gemini_input_audio(
    messages: list[dict[str, Any]],
    *,
    logger: logging.Logger | None = None,
) -> None:
    for msg in messages:
        content = msg.get('content')
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            await transform_message_part_for_gemini_input_audio(part, logger=logger)
