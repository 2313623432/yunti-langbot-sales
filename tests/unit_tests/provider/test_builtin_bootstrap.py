from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.entity.errors import provider as provider_errors
from langbot.pkg.provider.modelmgr import builtin_asr_providers, builtin_bootstrap, builtin_tts_providers


@pytest.mark.asyncio
async def test_ensure_builtin_tts_providers_creates_openai_tts_model():
    openai_spec = builtin_tts_providers.get_builtin_tts_provider_spec('lnv-openai')
    assert openai_spec is not None

    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.persistence_mgr = AsyncMock()
    mock_app.persistence_mgr.execute_async = AsyncMock(
        return_value=Mock(first=Mock(return_value=None))
    )
    mock_app.model_mgr = AsyncMock()
    mock_app.model_mgr.load_provider = AsyncMock(return_value=Mock())
    mock_app.model_mgr.provider_dict = {}
    mock_app.llm_model_service = AsyncMock()
    mock_app.llm_model_service.create_llm_model = AsyncMock()

    await builtin_bootstrap._ensure_provider(mock_app, openai_spec)
    await builtin_bootstrap._ensure_tts_model(mock_app, openai_spec.uuid, openai_spec.models[0])

    model_args = mock_app.llm_model_service.create_llm_model.await_args_list[0].args[0]
    assert model_args['provider_uuid'] == 'lnv-openai'
    assert model_args['abilities'] == ['tts']


@pytest.mark.asyncio
async def test_ensure_builtin_asr_providers_skips_missing_requester(monkeypatch):
    missing_spec = builtin_asr_providers.BuiltinASRProviderSpec(
        uuid='missing-provider',
        name='Missing Provider',
        requester='missing-requester',
        base_url='https://example.test',
        protocol='openai',
        api_key_required=True,
        sort_order=999,
        models=(
            builtin_asr_providers.BuiltinASRModelSpec(
                uuid='missing-model',
                model_id='missing-model',
                display_name='Missing Model',
            ),
        ),
    )
    monkeypatch.setattr(
        builtin_asr_providers,
        'BUILTIN_ASR_PROVIDER_SPECS',
        (missing_spec,),
    )

    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.persistence_mgr = AsyncMock()
    mock_app.persistence_mgr.execute_async = AsyncMock(
        return_value=Mock(first=Mock(return_value=None))
    )
    mock_app.model_mgr = SimpleNamespace(
        load_provider=AsyncMock(side_effect=provider_errors.RequesterNotFoundError('missing-requester')),
        provider_dict={},
    )
    mock_app.llm_model_service = SimpleNamespace(create_llm_model=AsyncMock())

    await builtin_bootstrap.ensure_builtin_asr_providers(mock_app)

    assert mock_app.persistence_mgr.execute_async.await_count == 1
    mock_app.llm_model_service.create_llm_model.assert_not_awaited()
    mock_app.logger.warning.assert_called_once()
