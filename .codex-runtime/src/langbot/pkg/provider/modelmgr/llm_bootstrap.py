from __future__ import annotations

import sqlalchemy

from langbot.pkg.core import app
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.provider.modelmgr import builtin_text_providers


async def ensure_builtin_text_providers(ap: app.Application) -> None:
    """Ensure built-in text model providers and their default models exist."""
    for provider_spec in builtin_text_providers.BUILTIN_TEXT_PROVIDER_SPECS:
        await _ensure_provider(ap, provider_spec)
        for model_spec in provider_spec.models:
            await _ensure_model(ap, provider_spec.uuid, model_spec)


async def _ensure_provider(
    ap: app.Application,
    provider_spec: builtin_text_providers.BuiltinTextProviderSpec,
) -> None:
    provider_result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_model.ModelProvider).where(
            persistence_model.ModelProvider.uuid == provider_spec.uuid
        )
    )
    if provider_result.first() is not None:
        return

    provider_data = {
        'uuid': provider_spec.uuid,
        'name': provider_spec.name,
        'requester': provider_spec.requester,
        'base_url': provider_spec.base_url,
        'api_keys': [],
    }
    await ap.persistence_mgr.execute_async(
        sqlalchemy.insert(persistence_model.ModelProvider).values(provider_data)
    )
    runtime_provider = await ap.model_mgr.load_provider(provider_data)
    ap.model_mgr.provider_dict[provider_spec.uuid] = runtime_provider
    ap.logger.info('Created built-in text provider: %s', provider_spec.name)


async def _ensure_model(
    ap: app.Application,
    provider_uuid: str,
    model_spec: builtin_text_providers.BuiltinTextModelSpec,
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
            'abilities': list(model_spec.abilities),
            'extra_args': model_spec.to_extra_args(),
            'prefered_ranking': 0,
        },
        preserve_uuid=True,
        auto_set_to_default_pipeline=False,
    )
    ap.logger.info('Created built-in text model: %s (%s)', model_spec.display_name, model_spec.model_id)
