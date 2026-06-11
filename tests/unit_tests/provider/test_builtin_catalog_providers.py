from __future__ import annotations

from langbot.pkg.provider.modelmgr import (
    builtin_asr_providers,
    builtin_embedding_providers,
    builtin_pdf_providers,
    builtin_registry,
    builtin_tts_providers,
)


def test_tts_catalog_contains_seven_providers():
    catalog = builtin_tts_providers.get_builtin_tts_catalog()
    provider_uuids = {item['uuid'] for item in catalog}

    assert 'lnv-openai' in provider_uuids
    assert 'lnv-azure' in provider_uuids
    assert 'lnv-zhipu' in provider_uuids
    assert 'lnv-qwen' in provider_uuids
    assert 'lnv-minimax' in provider_uuids
    assert 'lnv-doubao' in provider_uuids
    assert 'lnv-elevenlabs' in provider_uuids
    assert len(catalog) == 7


def test_tts_models_use_tts_ability_only():
    openai = builtin_tts_providers.get_builtin_tts_provider_spec('lnv-openai')
    assert openai is not None
    assert {model.model_id for model in openai.models} == {
        'gpt-4o-mini-tts',
        'tts-1',
        'tts-1-hd',
    }


def test_embedding_catalog_contains_common_providers():
    catalog = builtin_embedding_providers.get_builtin_embedding_catalog()
    provider_uuids = {item['uuid'] for item in catalog}

    assert 'lne-openai' in provider_uuids
    assert 'lne-zhipu' in provider_uuids
    assert 'lne-qwen' in provider_uuids
    assert 'lne-deepseek' in provider_uuids
    assert 'lne-siliconflow' in provider_uuids
    assert 'lne-ollama' not in provider_uuids
    assert 'lne-baidu-aistudio-embedding-provider' in provider_uuids


def test_pdf_catalog_contains_expected_providers():
    catalog = builtin_pdf_providers.get_builtin_pdf_catalog()
    provider_uuids = {item['uuid'] for item in catalog}

    assert provider_uuids == {
        'lno-unpdf',
        'lno-mineru-cloud',
        'lno-paddleocr',
    }


def test_tts_minimax_provider_uses_claude_protocol():
    from langbot.pkg.provider.modelmgr import builtin_tts_providers

    spec = builtin_tts_providers.get_builtin_tts_provider_spec('lnv-minimax')
    assert spec is not None
    assert spec.protocol == 'claude'


def test_doubao_tts_requires_one_api_key():
    provider = builtin_registry.enrich_provider_dict(
        {
            'uuid': 'lnv-doubao',
            'requester': 'openai-chat-completions',
            'base_url': 'https://openspeech.bytedance.com',
            'api_keys': [],
        }
    )

    assert provider['required_api_key_count'] == 1
    assert builtin_registry.is_provider_configured(provider, model_count=1) is False

    configured = dict(provider)
    configured['api_keys'] = ['speech-api-key']
    assert builtin_registry.is_provider_configured(configured, model_count=1) is True

    spec = builtin_tts_providers.get_builtin_tts_provider_spec('lnv-doubao')
    assert spec is not None
    assert spec.models[0].model_id == 'seed-tts-2.0-standard'


def test_asr_catalog_contains_doubao_api_key_provider():
    catalog = builtin_asr_providers.get_builtin_asr_catalog()
    provider_uuids = {item['uuid'] for item in catalog}

    assert 'lna-doubao' in provider_uuids

    doubao = builtin_asr_providers.get_builtin_asr_provider_spec('lna-doubao')
    assert doubao is not None
    assert doubao.requester == 'volcengine-asr'
    assert doubao.required_api_key_count == 1
    assert doubao.models[0].uuid == 'lna-doubao-bigasr-flash'

    provider = builtin_registry.enrich_provider_dict(
        {
            'uuid': 'lna-doubao',
            'requester': 'volcengine-asr',
            'base_url': 'https://openspeech.bytedance.com',
            'api_keys': ['speech-api-key'],
        }
    )
    assert builtin_registry.is_provider_configured(provider, model_count=1) is True


def test_unpdf_provider_does_not_require_api_key():
    provider = builtin_registry.enrich_provider_dict(
        {
            'uuid': 'lno-unpdf',
            'requester': 'builtin-pdf-parse',
            'base_url': 'local://pdf',
            'api_keys': [],
        }
    )

    assert builtin_registry.is_provider_configured(provider, model_count=1) is True
