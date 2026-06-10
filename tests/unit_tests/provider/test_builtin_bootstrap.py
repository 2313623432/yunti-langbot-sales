from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.provider.modelmgr import builtin_bootstrap, builtin_tts_providers


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
