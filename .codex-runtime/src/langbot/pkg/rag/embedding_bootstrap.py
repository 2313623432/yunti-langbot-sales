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


async def resolve_preferred_embedding_model_uuid(ap: app.Application) -> str | None:
    """Return the best available embedding model UUID for knowledge base defaults."""
    await ensure_default_embedding_model(ap)

    for candidate in PREFERRED_EMBEDDING_MODEL_UUIDS:
        if await _is_usable_embedding_model_uuid(ap, candidate):
            return candidate

    result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_model.EmbeddingModel).order_by(
            persistence_model.EmbeddingModel.prefered_ranking
        )
    )
    for row in result.all():
        model_data = ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, row)
        model_uuid = str(model_data.get('uuid') or '').strip()
        if await _is_usable_embedding_model_uuid(ap, model_uuid):
            return model_uuid
    return None


async def _is_usable_embedding_model_uuid(ap: app.Application, model_uuid: str) -> bool:
    if not model_uuid or model_uuid in DEPRECATED_EMBEDDING_MODEL_UUIDS:
        return False

    model_result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_model.EmbeddingModel).where(
            persistence_model.EmbeddingModel.uuid == model_uuid
        )
    )
    model_row = model_result.first()
    if model_row is None:
        return False

    model_data = ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, model_row)
    provider_uuid = str(model_data.get('provider_uuid') or '').strip()
    if not provider_uuid:
        return False

    provider_result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_model.ModelProvider).where(
            persistence_model.ModelProvider.uuid == provider_uuid
        )
    )
    provider_row = provider_result.first()
    if provider_row is None:
        return False

    provider_data = ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider_row)
    api_keys = provider_data.get('api_keys') or []
    return bool(api_keys) and bool(str(provider_data.get('base_url') or '').strip())


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
