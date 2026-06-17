from __future__ import annotations

from langbot.pkg.provider.modelmgr import builtin_text_providers


def test_builtin_text_catalog_contains_expected_providers():
    catalog = builtin_text_providers.get_builtin_text_catalog()
    provider_uuids = {item['uuid'] for item in catalog}

    assert 'lnp-openai' in provider_uuids
    assert 'lnp-claude' in provider_uuids
    assert 'lnp-gemini' in provider_uuids
    assert 'lnp-ollama' not in provider_uuids
    assert len(catalog) == len(builtin_text_providers.BUILTIN_TEXT_PROVIDER_SPECS)


def test_enrich_provider_dict_marks_builtin_metadata():
    enriched = builtin_text_providers.enrich_provider_dict(
        {
            'uuid': 'lnp-openai',
            'name': 'OpenAI',
            'requester': 'openai-chat-completions',
            'base_url': 'https://api.openai.com/v1',
            'api_keys': [],
        }
    )

    assert enriched['is_builtin'] is True
    assert enriched['protocol'] == 'openai'
    assert enriched['api_key_required'] is True
    assert enriched['sort_order'] == 10


def test_openai_catalog_models_include_gpt_4o():
    spec = builtin_text_providers.get_builtin_text_provider_spec('lnp-openai')
    assert spec is not None
    model_ids = {model.model_id for model in spec.models}
    assert 'gpt-4o' in model_ids
    assert 'gpt-5.4' in model_ids


def test_doubao_catalog_excludes_removed_placeholder_models():
    from langbot.pkg.provider.modelmgr import llm_bootstrap

    spec = builtin_text_providers.get_builtin_text_provider_spec('lnp-doubao')
    assert spec is not None

    catalog_model_uuids = {model.uuid for model in spec.models}
    assert catalog_model_uuids.isdisjoint(
        llm_bootstrap.REMOVED_DOUBAO_TEXT_MODEL_UUIDS
    )
    assert builtin_text_providers.BUILTIN_TEXT_MODEL_UUIDS.isdisjoint(
        llm_bootstrap.REMOVED_DOUBAO_TEXT_MODEL_UUIDS
    )


def test_doubao_catalog_includes_seed_2_models_with_thinking_settings():
    spec = builtin_text_providers.get_builtin_text_provider_spec('lnp-doubao')
    assert spec is not None

    models = {model.model_id: model for model in spec.models}
    assert 'doubao-seed-2-0-mini-260215' in models
    assert 'doubao-seed-2-0-pro-260215' in models
    assert models['doubao-seed-2-0-mini-260215'].to_extra_args()['thinking'] == {'type': 'disabled'}
    assert models['doubao-seed-2-0-pro-260215'].to_extra_args()['reasoning_effort'] == 'low'


def test_is_provider_configured_requires_base_url_api_key_and_models():
    provider = {
        'uuid': 'lnp-openai',
        'requester': 'openai-chat-completions',
        'base_url': 'https://api.openai.com/v1',
        'api_keys': ['sk-test'],
    }
    enriched = builtin_text_providers.enrich_provider_dict(provider)

    assert builtin_text_providers.is_provider_configured(enriched, model_count=1) is True
    assert builtin_text_providers.is_provider_configured(enriched, model_count=0) is False
    assert (
        builtin_text_providers.is_provider_configured(
            {**enriched, 'api_keys': []},
            model_count=1,
        )
        is False
    )
    assert (
        builtin_text_providers.is_provider_configured(
            {**enriched, 'base_url': '   '},
            model_count=1,
        )
        is False
    )


def test_is_provider_configured_allows_no_api_key_requester_without_api_key():
    provider = builtin_text_providers.enrich_provider_dict(
        {
            'uuid': 'custom-lmstudio',
            'requester': 'lmstudio-chat-completions',
            'base_url': 'http://127.0.0.1:1234/v1',
            'api_keys': [],
        }
    )

    assert builtin_text_providers.is_provider_configured(provider, model_count=1) is True


def test_provider_requires_api_key_for_custom_ollama_requester():
    provider = {
        'uuid': 'custom-ollama',
        'requester': 'ollama-chat',
        'base_url': 'http://127.0.0.1:11434',
        'api_keys': [],
    }

    assert builtin_text_providers.provider_requires_api_key(provider) is False
    assert builtin_text_providers.is_provider_configured(provider, model_count=1) is True
