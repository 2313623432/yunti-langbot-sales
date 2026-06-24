from __future__ import annotations

from langbot.pkg.provider.modelmgr.builtin_protocol import (
    default_requester_for_protocol,
    infer_protocol_from_requester,
    validate_protocol,
)

NO_API_KEY_REQUESTERS = frozenset(
    {
        'ollama-chat',
        'lmstudio-chat-completions',
        'builtin-pdf-parse',
    }
)


def _normalize_api_keys(api_keys: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if api_keys is None:
        return []

    raw_keys = [api_keys] if isinstance(api_keys, str) else list(api_keys)
    normalized_keys = []
    seen_keys = set()

    for raw_key in raw_keys:
        normalized_key = raw_key.strip() if isinstance(raw_key, str) else ''
        if not normalized_key or normalized_key in seen_keys:
            continue
        normalized_keys.append(normalized_key)
        seen_keys.add(normalized_key)

    return normalized_keys


def provider_requires_api_key(provider_dict: dict) -> bool:
    if 'api_key_required' in provider_dict:
        return bool(provider_dict['api_key_required'])
    return provider_dict.get('requester', '') not in NO_API_KEY_REQUESTERS


def required_api_key_count(provider_dict: dict) -> int:
    count = provider_dict.get('required_api_key_count')
    if isinstance(count, int) and count > 0:
        return count
    return 1 if provider_requires_api_key(provider_dict) else 0


def is_provider_configured(provider_dict: dict, *, model_count: int = 1) -> bool:
    """Return True when a provider is ready for model selection dropdowns."""
    if model_count <= 0:
        return False

    base_url = (provider_dict.get('base_url') or '').strip()
    if not base_url and provider_requires_api_key(provider_dict):
        return False

    required_keys = required_api_key_count(provider_dict)
    if required_keys <= 0:
        return True

    api_keys = provider_dict.get('api_keys')
    if isinstance(api_keys, str):
        import json

        try:
            api_keys = json.loads(api_keys)
        except Exception:
            api_keys = []
    if len(_normalize_api_keys(api_keys)) < required_keys:
        return False

    return True


def enrich_provider_dict(provider_dict: dict, builtin_lookup: dict[str, dict]) -> dict:
    spec = builtin_lookup.get(provider_dict.get('uuid', ''))
    if spec is None:
        provider_dict.setdefault('is_builtin', False)
        if 'protocol' not in provider_dict:
            provider_dict['protocol'] = infer_protocol_from_requester(
                provider_dict.get('requester', ''),
                provider_uuid=provider_dict.get('uuid'),
            )
        return provider_dict

    provider_dict['is_builtin'] = True
    provider_dict['requester'] = spec.get('requester', provider_dict.get('requester'))
    provider_dict['protocol'] = spec.get('protocol', provider_dict.get('protocol'))
    provider_dict['api_key_required'] = spec.get('api_key_required', True)
    provider_dict['required_api_key_count'] = spec.get('required_api_key_count', 1 if spec.get('api_key_required', True) else 0)
    provider_dict['sort_order'] = spec.get('sort_order', 999)
    provider_dict['provider_kind'] = spec.get('provider_kind')
    return provider_dict
