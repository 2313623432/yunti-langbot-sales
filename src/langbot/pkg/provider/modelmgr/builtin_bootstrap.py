from __future__ import annotations

import sqlalchemy

from langbot.pkg.core import app
from langbot.pkg.entity.errors import provider as provider_errors
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.provider.modelmgr import (
    builtin_asr_providers,
    builtin_embedding_providers,
    builtin_pdf_providers,
    builtin_tts_providers,
)


async def ensure_builtin_asr_providers(ap: app.Application) -> None:
    for provider_spec in builtin_asr_providers.BUILTIN_ASR_PROVIDER_SPECS:
        if not await _ensure_provider(ap, provider_spec):
            continue
        for model_spec in provider_spec.models:
            await _ensure_asr_model(ap, provider_spec.uuid, model_spec)


async def ensure_builtin_tts_providers(ap: app.Application) -> None:
    for provider_spec in builtin_tts_providers.BUILTIN_TTS_PROVIDER_SPECS:
        if not await _ensure_provider(ap, provider_spec):
            continue
        for model_spec in provider_spec.models:
            await _ensure_tts_model(ap, provider_spec.uuid, model_spec)


REMOVED_PDF_PROVIDER_UUIDS = frozenset({'lno-mineru-local'})
REMOVED_PDF_MODEL_UUIDS = frozenset({'lno-mineru-local-default'})

REMOVED_OLLAMA_TEXT_PROVIDER_UUIDS = frozenset({'lnp-ollama'})
REMOVED_OLLAMA_TEXT_MODEL_UUIDS = frozenset(
    {
        'lnp-ollama-llama3-2',
        'lnp-ollama-qwen2-5',
        'lnp-ollama-deepseek-r1',
    }
)
REMOVED_OLLAMA_EMBEDDING_PROVIDER_UUIDS = frozenset({'lne-ollama'})
REMOVED_OLLAMA_EMBEDDING_MODEL_UUIDS = frozenset(
    {
        'lne-ollama-nomic-embed',
        'lne-ollama-bge-m3',
    }
)


async def ensure_builtin_pdf_providers(ap: app.Application) -> None:
    await _prune_removed_pdf_providers(ap)
    for provider_spec in builtin_pdf_providers.BUILTIN_PDF_PROVIDER_SPECS:
        if not await _ensure_provider(ap, provider_spec):
            continue
        for model_spec in provider_spec.models:
            await _ensure_pdf_model(ap, provider_spec.uuid, model_spec)


async def _prune_removed_pdf_providers(ap: app.Application) -> None:
    for model_uuid in REMOVED_PDF_MODEL_UUIDS:
        await ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.LLMModel).where(
                persistence_model.LLMModel.uuid == model_uuid
            )
        )
        await ap.model_mgr.remove_llm_model(model_uuid)
    for provider_uuid in REMOVED_PDF_PROVIDER_UUIDS:
        await ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == provider_uuid
            )
        )
        ap.model_mgr.provider_dict.pop(provider_uuid, None)


async def prune_removed_ollama_providers(ap: app.Application) -> None:
    for model_uuid in REMOVED_OLLAMA_TEXT_MODEL_UUIDS:
        await ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.LLMModel).where(
                persistence_model.LLMModel.uuid == model_uuid
            )
        )
        await ap.model_mgr.remove_llm_model(model_uuid)
    for provider_uuid in REMOVED_OLLAMA_TEXT_PROVIDER_UUIDS:
        await ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == provider_uuid
            )
        )
        ap.model_mgr.provider_dict.pop(provider_uuid, None)

    for model_uuid in REMOVED_OLLAMA_EMBEDDING_MODEL_UUIDS:
        await ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.EmbeddingModel).where(
                persistence_model.EmbeddingModel.uuid == model_uuid
            )
        )
        await ap.model_mgr.remove_embedding_model(model_uuid)
    for provider_uuid in REMOVED_OLLAMA_EMBEDDING_PROVIDER_UUIDS:
        await ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == provider_uuid
            )
        )
        ap.model_mgr.provider_dict.pop(provider_uuid, None)


async def ensure_builtin_embedding_providers(ap: app.Application) -> None:
    for provider_spec in builtin_embedding_providers.BUILTIN_EMBEDDING_PROVIDER_SPECS:
        if not await _ensure_provider(ap, provider_spec):
            continue
        for model_spec in provider_spec.models:
            await _ensure_embedding_model(ap, provider_spec.uuid, model_spec)


async def _ensure_provider(ap: app.Application, provider_spec) -> bool:
    provider_result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_model.ModelProvider).where(
            persistence_model.ModelProvider.uuid == provider_spec.uuid
        )
    )
    existing_provider = provider_result.first()
    if existing_provider is not None:
        requester_changed = False
        if existing_provider.requester != provider_spec.requester:
            await ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_model.ModelProvider)
                .where(persistence_model.ModelProvider.uuid == provider_spec.uuid)
                .values(requester=provider_spec.requester)
            )
            refreshed_provider_result = await ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_model.ModelProvider).where(
                    persistence_model.ModelProvider.uuid == provider_spec.uuid
                )
            )
            existing_provider = refreshed_provider_result.first() or existing_provider
            requester_changed = True
        if provider_spec.uuid in ap.model_mgr.provider_dict and not requester_changed:
            return True
        try:
            runtime_provider = await ap.model_mgr.load_provider(existing_provider)
        except provider_errors.RequesterNotFoundError as e:
            ap.logger.warning('Requester %s not found, skipping built-in provider %s', e.requester_name, provider_spec.uuid)
            return False
        ap.model_mgr.provider_dict[provider_spec.uuid] = runtime_provider
        return True

    provider_data = {
        'uuid': provider_spec.uuid,
        'name': provider_spec.name,
        'requester': provider_spec.requester,
        'base_url': provider_spec.base_url,
        'api_keys': [],
    }
    try:
        runtime_provider = await ap.model_mgr.load_provider(provider_data)
    except provider_errors.RequesterNotFoundError as e:
        ap.logger.warning('Requester %s not found, skipping built-in provider %s', e.requester_name, provider_spec.uuid)
        return False

    await ap.persistence_mgr.execute_async(
        sqlalchemy.insert(persistence_model.ModelProvider).values(provider_data)
    )
    ap.model_mgr.provider_dict[provider_spec.uuid] = runtime_provider
    ap.logger.info('Created built-in provider: %s', provider_spec.name)
    return True


async def _ensure_tts_model(
    ap: app.Application,
    provider_uuid: str,
    model_spec: builtin_tts_providers.BuiltinTTSModelSpec,
) -> None:
    existing = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_model.LLMModel).where(
            persistence_model.LLMModel.uuid == model_spec.uuid
        )
    )
    existing_row = existing.first()
    desired_extra_args = model_spec.to_extra_args()
    if existing_row is not None:
        current_extra_args = existing_row.extra_args if isinstance(existing_row.extra_args, dict) else {}
        merged_extra_args = {**current_extra_args, **desired_extra_args}
        if merged_extra_args != current_extra_args:
            await ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_model.LLMModel)
                .where(persistence_model.LLMModel.uuid == model_spec.uuid)
                .values(extra_args=merged_extra_args)
            )
            runtime_model = next(
                (model for model in ap.model_mgr.llm_models if model.model_entity.uuid == model_spec.uuid),
                None,
            )
            if runtime_model is not None:
                runtime_model.model_entity.extra_args = merged_extra_args
        return

    await ap.llm_model_service.create_llm_model(
        {
            'uuid': model_spec.uuid,
            'name': model_spec.model_id,
            'provider_uuid': provider_uuid,
            'abilities': ['tts'],
            'extra_args': model_spec.to_extra_args(),
            'prefered_ranking': 0,
        },
        preserve_uuid=True,
        auto_set_to_default_pipeline=False,
    )
    ap.logger.info('Created built-in TTS model: %s (%s)', model_spec.display_name, model_spec.model_id)


async def _ensure_asr_model(
    ap: app.Application,
    provider_uuid: str,
    model_spec: builtin_asr_providers.BuiltinASRModelSpec,
) -> None:
    existing = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_model.LLMModel).where(
            persistence_model.LLMModel.uuid == model_spec.uuid
        )
    )
    existing_row = existing.first()
    desired_extra_args = model_spec.to_extra_args()
    if existing_row is not None:
        current_extra_args = existing_row.extra_args if isinstance(existing_row.extra_args, dict) else {}
        merged_extra_args = {**current_extra_args, **desired_extra_args}
        if merged_extra_args != current_extra_args:
            await ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_model.LLMModel)
                .where(persistence_model.LLMModel.uuid == model_spec.uuid)
                .values(extra_args=merged_extra_args)
            )
            runtime_model = next(
                (model for model in ap.model_mgr.llm_models if model.model_entity.uuid == model_spec.uuid),
                None,
            )
            if runtime_model is not None:
                runtime_model.model_entity.extra_args = merged_extra_args
        return

    await ap.llm_model_service.create_llm_model(
        {
            'uuid': model_spec.uuid,
            'name': model_spec.model_id,
            'provider_uuid': provider_uuid,
            'abilities': ['asr'],
            'extra_args': desired_extra_args,
            'prefered_ranking': 0,
        },
        preserve_uuid=True,
        auto_set_to_default_pipeline=False,
    )
    ap.logger.info('Created built-in ASR model: %s (%s)', model_spec.display_name, model_spec.model_id)


async def _ensure_pdf_model(
    ap: app.Application,
    provider_uuid: str,
    model_spec: builtin_pdf_providers.BuiltinPdfModelSpec,
) -> None:
    existing = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_model.LLMModel).where(
            persistence_model.LLMModel.uuid == model_spec.uuid
        )
    )
    if existing.first() is not None:
        return

    await ap.llm_model_service.create_llm_model(
        {
            'uuid': model_spec.uuid,
            'name': model_spec.model_id,
            'provider_uuid': provider_uuid,
            'abilities': ['pdf_parse'],
            'extra_args': model_spec.to_extra_args(),
            'prefered_ranking': 0,
        },
        preserve_uuid=True,
        auto_set_to_default_pipeline=False,
    )
    ap.logger.info('Created built-in PDF model: %s (%s)', model_spec.display_name, model_spec.model_id)


async def _ensure_embedding_model(
    ap: app.Application,
    provider_uuid: str,
    model_spec: builtin_embedding_providers.BuiltinEmbeddingModelSpec,
) -> None:
    existing = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_model.EmbeddingModel).where(
            persistence_model.EmbeddingModel.uuid == model_spec.uuid
        )
    )
    if existing.first() is not None:
        return

    await ap.embedding_models_service.create_embedding_model(
        {
            'uuid': model_spec.uuid,
            'name': model_spec.display_name,
            'provider_uuid': provider_uuid,
            'extra_args': model_spec.to_extra_args(),
            'prefered_ranking': model_spec.prefered_ranking,
        },
        preserve_uuid=True,
    )
    ap.logger.info('Created built-in embedding model: %s', model_spec.display_name)
