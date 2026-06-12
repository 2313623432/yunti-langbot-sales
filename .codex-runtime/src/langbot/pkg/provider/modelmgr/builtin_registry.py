from __future__ import annotations

from langbot.pkg.provider.modelmgr import builtin_provider_common


def _catalog_lookup() -> dict[str, dict]:
    from langbot.pkg.provider.modelmgr import (
        builtin_asr_providers,
        builtin_embedding_providers,
        builtin_pdf_providers,
        builtin_text_providers,
        builtin_tts_providers,
    )

    lookup: dict[str, dict] = {}
    for spec in builtin_text_providers.BUILTIN_TEXT_PROVIDER_SPECS:
        lookup[spec.uuid] = {
            'protocol': spec.protocol,
            'api_key_required': spec.api_key_required,
            'required_api_key_count': 1 if spec.api_key_required else 0,
            'sort_order': spec.sort_order,
            'provider_kind': 'text',
        }
    for spec in builtin_tts_providers.BUILTIN_TTS_PROVIDER_SPECS:
        lookup[spec.uuid] = {
            'protocol': spec.protocol,
            'api_key_required': spec.api_key_required,
            'required_api_key_count': spec.required_api_key_count,
            'sort_order': spec.sort_order,
            'provider_kind': spec.provider_kind,
        }
    for spec in builtin_asr_providers.BUILTIN_ASR_PROVIDER_SPECS:
        lookup[spec.uuid] = {
            'protocol': spec.protocol,
            'api_key_required': spec.api_key_required,
            'required_api_key_count': spec.required_api_key_count,
            'sort_order': spec.sort_order,
            'provider_kind': spec.provider_kind,
        }
    for spec in builtin_embedding_providers.BUILTIN_EMBEDDING_PROVIDER_SPECS:
        lookup[spec.uuid] = {
            'protocol': spec.protocol,
            'api_key_required': spec.api_key_required,
            'required_api_key_count': 0 if not spec.api_key_required else 1,
            'sort_order': spec.sort_order,
            'provider_kind': spec.provider_kind,
        }
    for spec in builtin_pdf_providers.BUILTIN_PDF_PROVIDER_SPECS:
        lookup[spec.uuid] = {
            'protocol': spec.protocol,
            'api_key_required': spec.api_key_required,
            'required_api_key_count': 0 if not spec.api_key_required else 1,
            'sort_order': spec.sort_order,
            'provider_kind': spec.provider_kind,
        }
    return lookup


_CATALOG_LOOKUP: dict[str, dict] | None = None


def _get_catalog_lookup() -> dict[str, dict]:
    global _CATALOG_LOOKUP
    if _CATALOG_LOOKUP is None:
        _CATALOG_LOOKUP = _catalog_lookup()
    return _CATALOG_LOOKUP


def all_builtin_provider_uuids() -> frozenset[str]:
    return frozenset(_get_catalog_lookup().keys())


def is_builtin_provider(provider_uuid: str | None) -> bool:
    return provider_uuid in _get_catalog_lookup()


def enrich_provider_dict(provider_dict: dict) -> dict:
    return builtin_provider_common.enrich_provider_dict(provider_dict, _get_catalog_lookup())


def is_provider_configured(provider_dict: dict, *, model_count: int = 1) -> bool:
    enriched = enrich_provider_dict(dict(provider_dict))
    return builtin_provider_common.is_provider_configured(enriched, model_count=model_count)


def provider_requires_api_key(provider_dict: dict) -> bool:
    enriched = enrich_provider_dict(dict(provider_dict))
    return builtin_provider_common.provider_requires_api_key(enriched)
