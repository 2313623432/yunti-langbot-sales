from __future__ import annotations

import pytest

from langbot.pkg.provider.modelmgr import builtin_registry, builtin_text_providers
from langbot.pkg.provider.modelmgr.builtin_protocol import (
    default_requester_for_protocol,
    infer_protocol_from_requester,
    validate_protocol,
)


def test_validate_protocol_accepts_known_values():
    assert validate_protocol('openai') == 'openai'
    assert validate_protocol('claude') == 'claude'
    assert validate_protocol('gemini') == 'gemini'
    assert validate_protocol(None) is None


def test_validate_protocol_rejects_unknown_value():
    with pytest.raises(ValueError, match='Invalid protocol'):
        validate_protocol('ollama')


def test_default_requester_for_protocol():
    assert default_requester_for_protocol('openai') == 'openai-chat-completions'
    assert default_requester_for_protocol('claude') == 'anthropic-messages'
    assert default_requester_for_protocol('gemini') == 'gemini-chat-completions'


def test_infer_protocol_from_requester():
    assert infer_protocol_from_requester('anthropic-messages') == 'claude'
    assert infer_protocol_from_requester('gemini-chat-completions') == 'gemini'
    assert infer_protocol_from_requester('zhipuai-chat-completions') == 'openai'
    assert infer_protocol_from_requester('openai-chat-completions', provider_uuid='lnp-minimax') == 'claude'


def test_minimax_text_provider_uses_claude_protocol():
    spec = builtin_text_providers.get_builtin_text_provider_spec('lnp-minimax')
    assert spec is not None
    assert spec.protocol == 'claude'


def test_enrich_minimax_provider_dict():
    enriched = builtin_registry.enrich_provider_dict(
        {
            'uuid': 'lnp-minimax',
            'requester': 'openai-chat-completions',
            'base_url': 'https://api.minimax.chat/v1',
            'api_keys': [],
        }
    )
    assert enriched['protocol'] == 'claude'


def test_enrich_custom_provider_infers_openai_protocol():
    enriched = builtin_registry.enrich_provider_dict(
        {
            'uuid': 'custom-zhipu',
            'requester': 'zhipuai-chat-completions',
            'base_url': 'https://open.bigmodel.cn/api/paas/v4',
            'api_keys': [],
        }
    )
    assert enriched['protocol'] == 'openai'
    assert enriched['is_builtin'] is False
