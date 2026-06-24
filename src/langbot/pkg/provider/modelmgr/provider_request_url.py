from __future__ import annotations

from langbot.pkg.provider.modelmgr.tts_invoke import _volcengine_http_url, resolve_dashscope_tts_url

ModelCategory = str


def _normalize_base_url(base_url: str) -> str:
    return (base_url or '').strip().rstrip('/')


def resolve_text_request_url(requester: str = '', base_url: str = '') -> str:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return ''

    if '/chat/completions' in normalized:
        return normalized

    requester_name = (requester or '').lower()
    if requester_name == 'anthropic-messages':
        if normalized.endswith('/v1/messages'):
            return normalized
        return f'{normalized}/v1/messages'
    if requester_name == 'ollama-chat':
        return f'{normalized}/api/chat'

    return f'{normalized}/chat/completions'


def resolve_embedding_request_url(requester: str = '', base_url: str = '') -> str:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return ''

    if '/embeddings' in normalized or normalized.endswith('/embed'):
        return normalized

    requester_name = (requester or '').lower()
    if requester_name == 'ollama-chat':
        return f'{normalized}/api/embed'

    return f'{normalized}/embeddings'


def resolve_voice_request_url(requester: str = '', base_url: str = '') -> str:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return ''

    requester_name = (requester or '').lower()

    if requester_name == 'azure-tts':
        return f'{normalized}/cognitiveservices/v1'
    if requester_name == 'elevenlabs-tts':
        return f'{normalized}/text-to-speech/{{voice_id}}'
    if requester_name == 'volcengine-tts':
        return _volcengine_http_url(normalized)
    if (
        requester_name in {'bailian-chat-completions', 'dashscope-tts'}
        or 'dashscope.aliyuncs.com' in normalized
    ):
        return resolve_dashscope_tts_url(normalized)
    if requester_name == 'zhipuai-chat-completions' or 'bigmodel.cn' in normalized:
        return f'{normalized}/audio/speech'
    if 'minimax' in normalized:
        return f'{normalized}/v1/t2a_v2'
    if normalized.endswith('/v1'):
        return f'{normalized}/audio/speech'

    return normalized


def resolve_pdf_request_url(requester: str = '', base_url: str = '') -> str:
    raw_base_url = (base_url or '').strip()
    normalized = _normalize_base_url(raw_base_url)
    if not normalized:
        return ''

    requester_name = (requester or '').lower()
    if requester_name == 'builtin-pdf-parse':
        return raw_base_url
    if requester_name == 'mineru-cloud':
        return f'{normalized}/file-urls/batch'
    if requester_name == 'paddleocr-vl':
        return raw_base_url

    return raw_base_url


def resolve_provider_request_url(
    category: ModelCategory,
    requester: str = '',
    base_url: str = '',
) -> str:
    category_name = (category or '').lower()
    if category_name == 'voice':
        return resolve_voice_request_url(requester, base_url)
    if category_name == 'embedding':
        return resolve_embedding_request_url(requester, base_url)
    if category_name == 'pdf':
        return resolve_pdf_request_url(requester, base_url)
    return resolve_text_request_url(requester, base_url)
