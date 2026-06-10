from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.provider.modelmgr import llm_bootstrap


@pytest.mark.asyncio
async def test_ensure_builtin_text_providers_creates_openai_provider_and_models():
    from langbot.pkg.provider.modelmgr import builtin_text_providers

    openai_spec = builtin_text_providers.get_builtin_text_provider_spec('lnp-openai')
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

    await llm_bootstrap._ensure_provider(mock_app, openai_spec)
    await llm_bootstrap._ensure_model(mock_app, openai_spec.uuid, openai_spec.models[0])

    assert mock_app.model_mgr.load_provider.await_count == 1
    assert mock_app.llm_model_service.create_llm_model.await_count == 1

    first_model_args = mock_app.llm_model_service.create_llm_model.await_args_list[0].args[0]
    assert first_model_args['provider_uuid'] == 'lnp-openai'
    assert first_model_args['extra_args']['display_name']
