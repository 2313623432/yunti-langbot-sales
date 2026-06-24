from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch

from langbot.pkg.rag import embedding_bootstrap


@pytest.mark.asyncio
async def test_ensure_default_embedding_model_bootstraps_catalog():
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.persistence_mgr = AsyncMock()
    mock_app.model_mgr = AsyncMock()
    mock_app.model_mgr.reload_provider = AsyncMock()
    mock_app.embedding_models_service = AsyncMock()

    with patch(
        'langbot.pkg.rag.embedding_bootstrap.builtin_bootstrap.ensure_builtin_embedding_providers',
        new=AsyncMock(),
    ) as ensure_catalog:
        with patch.dict('os.environ', {}, clear=True):
            result = await embedding_bootstrap.ensure_default_embedding_model(mock_app)

    assert result == embedding_bootstrap.BAIDU_EMBEDDING_MODEL_UUID
    ensure_catalog.assert_awaited_once_with(mock_app)


@pytest.mark.asyncio
async def test_ensure_default_embedding_model_applies_baidu_env_api_key():
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.persistence_mgr = AsyncMock()
    mock_app.model_mgr = AsyncMock()
    mock_app.model_mgr.reload_provider = AsyncMock()

    with patch(
        'langbot.pkg.rag.embedding_bootstrap.builtin_bootstrap.ensure_builtin_embedding_providers',
        new=AsyncMock(),
    ):
        with patch.dict(
            'os.environ',
            {'LNE_BAIDU_EMBEDDING_API_KEY': 'baidu-key'},
            clear=False,
        ):
            await embedding_bootstrap.ensure_default_embedding_model(mock_app)

    mock_app.model_mgr.reload_provider.assert_awaited_once_with(
        embedding_bootstrap.BAIDU_EMBEDDING_PROVIDER_UUID
    )
