from __future__ import annotations

import os

import sqlalchemy

from langbot.pkg.core import app
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.provider.modelmgr import builtin_bootstrap

BAIDU_EMBEDDING_PROVIDER_UUID = 'lne-baidu-aistudio-embedding-provider'
BAIDU_EMBEDDING_MODEL_UUID = 'lne-baidu-bge-large-zh'
BAIDU_EMBEDDING_DISPLAY_NAME = '百度星河 bge-large-zh'
BAIDU_PROVIDER_NAME = '百度星河 Embedding'
BAIDU_BASE_URL = 'https://aistudio.baidu.com/llm/lmapi/v3'
BAIDU_MODEL_NAME = 'bge-large-zh'

PREFERRED_EMBEDDING_MODEL_UUIDS = (BAIDU_EMBEDDING_MODEL_UUID,)
DEPRECATED_EMBEDDING_MODEL_UUIDS = frozenset(
    {
        'lne-default-embedding-model',
        'a99c0949-e534-479c-8c6d-cae2d33ce4ae',
    }
)


async def ensure_default_embedding_model(ap: app.Application) -> str | None:
    """Ensure built-in embedding providers/models exist."""
    await builtin_bootstrap.ensure_builtin_embedding_providers(ap)
    await _apply_baidu_env_overrides(ap)
    return BAIDU_EMBEDDING_MODEL_UUID


async def _apply_baidu_env_overrides(ap: app.Application) -> None:
    api_key = (os.getenv('LNE_BAIDU_EMBEDDING_API_KEY') or '').strip()
    base_url = (os.getenv('LNE_BAIDU_EMBEDDING_BASE_URL') or '').strip()
    model_name = (os.getenv('LNE_BAIDU_EMBEDDING_MODEL') or '').strip()
    if not api_key and not base_url and not model_name:
        return

    values: dict = {}
    if api_key:
        values['api_keys'] = [api_key]
    if base_url:
        values['base_url'] = base_url
    if values:
        await ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_model.ModelProvider)
            .where(persistence_model.ModelProvider.uuid == BAIDU_EMBEDDING_PROVIDER_UUID)
            .values(**values)
        )
        await ap.model_mgr.reload_provider(BAIDU_EMBEDDING_PROVIDER_UUID)

    if model_name:
        existing = await ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.EmbeddingModel).where(
                persistence_model.EmbeddingModel.uuid == BAIDU_EMBEDDING_MODEL_UUID
            )
        )
        model = existing.first()
        if model is not None:
            extra_args = dict(model.extra_args or {})
            extra_args['model'] = model_name
            await ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_model.EmbeddingModel)
                .where(persistence_model.EmbeddingModel.uuid == BAIDU_EMBEDDING_MODEL_UUID)
                .values(extra_args=extra_args)
            )
