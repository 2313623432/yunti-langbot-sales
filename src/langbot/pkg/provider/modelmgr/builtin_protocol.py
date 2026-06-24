from __future__ import annotations

from typing import Literal

ProtocolType = Literal['openai', 'claude', 'gemini']

VALID_PROTOCOLS: frozenset[str] = frozenset({'openai', 'claude', 'gemini'})

DEFAULT_REQUESTER_BY_PROTOCOL: dict[str, str] = {
    'openai': 'openai-chat-completions',
    'claude': 'anthropic-messages',
    'gemini': 'gemini-chat-completions',
}

DEFAULT_BASE_URL_BY_PROTOCOL: dict[str, str] = {
    'openai': 'https://api.openai.com/v1',
    'claude': 'https://api.anthropic.com',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta/openai',
}

_CLAUDE_REQUESTERS = frozenset({'anthropic-messages'})
_GEMINI_REQUESTERS = frozenset({'gemini-chat-completions'})


def default_requester_for_protocol(protocol: str) -> str:
    return DEFAULT_REQUESTER_BY_PROTOCOL.get(protocol, 'openai-chat-completions')


def infer_protocol_from_requester(
    requester: str,
    *,
    provider_uuid: str | None = None,
) -> ProtocolType:
    if requester in _CLAUDE_REQUESTERS:
        return 'claude'
    if requester in _GEMINI_REQUESTERS:
        return 'gemini'

    normalized_uuid = (provider_uuid or '').lower()
    normalized_requester = (requester or '').lower()
    if 'minimax' in normalized_uuid or 'minimax' in normalized_requester:
        return 'claude'

    return 'openai'


def validate_protocol(protocol: str | None) -> ProtocolType | None:
    if protocol is None:
        return None
    if protocol not in VALID_PROTOCOLS:
        raise ValueError(f'Invalid protocol: {protocol}. Must be one of: openai, claude, gemini')
    return protocol  # type: ignore[return-value]
