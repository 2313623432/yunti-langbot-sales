from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langbot.pkg.core import app
from langbot.pkg.provider.modelmgr import builtin_registry
from langbot.pkg.provider.modelmgr import requester as model_requester
from langbot.pkg.rag.knowledge.document_text import extract_text_from_bytes


@dataclass(frozen=True)
class ResolvedPdfParseModel:
    runtime_model: model_requester.RuntimeLLMModel
    requester_name: str


def _provider_dict(runtime_model: model_requester.RuntimeLLMModel) -> dict[str, Any]:
    provider_entity = runtime_model.provider.provider_entity
    return builtin_registry.enrich_provider_dict(
        {
            'uuid': provider_entity.uuid,
            'requester': provider_entity.requester,
            'base_url': provider_entity.base_url,
            'api_keys': provider_entity.api_keys or [],
        }
    )


def _is_pdf_parse_model(runtime_model: model_requester.RuntimeLLMModel) -> bool:
    abilities = runtime_model.model_entity.abilities or []
    return 'pdf_parse' in abilities


def _is_configured_pdf_model(runtime_model: model_requester.RuntimeLLMModel) -> bool:
    if not _is_pdf_parse_model(runtime_model):
        return False
    return builtin_registry.is_provider_configured(_provider_dict(runtime_model))


def _auto_pdf_parse_sort_key(runtime_model: model_requester.RuntimeLLMModel) -> tuple:
    provider_entity = runtime_model.provider.provider_entity
    requester = provider_entity.requester
    ranking = runtime_model.model_entity.prefered_ranking or 0
    has_token = bool(provider_entity.api_keys or [])
    return (
        0 if has_token else 1,
        ranking,
        runtime_model.model_entity.uuid,
    )


def resolve_pdf_parse_models(
    ap: app.Application,
    pdf_model_uuid: str | None = None,
) -> list[ResolvedPdfParseModel]:
    model_mgr = getattr(ap, 'model_mgr', None)
    if model_mgr is None:
        return []

    if pdf_model_uuid:
        for runtime_model in model_mgr.llm_models:
            if runtime_model.model_entity.uuid == pdf_model_uuid and _is_pdf_parse_model(runtime_model):
                return [
                    ResolvedPdfParseModel(
                        runtime_model=runtime_model,
                        requester_name=runtime_model.provider.provider_entity.requester,
                    )
                ]
        return []

    configured_models = [
        runtime_model
        for runtime_model in model_mgr.llm_models
        if _is_configured_pdf_model(runtime_model)
    ]
    ocr_models = [
        runtime_model
        for runtime_model in configured_models
        if runtime_model.provider.provider_entity.requester != 'builtin-pdf-parse'
    ]
    if ocr_models:
        configured_models = ocr_models

    preferred = sorted(configured_models, key=_auto_pdf_parse_sort_key)
    resolved = [
        ResolvedPdfParseModel(
            runtime_model=runtime_model,
            requester_name=runtime_model.provider.provider_entity.requester,
        )
        for runtime_model in preferred
    ]
    if resolved:
        return resolved

    for runtime_model in model_mgr.llm_models:
        if runtime_model.provider.provider_entity.requester == 'builtin-pdf-parse':
            return [
                ResolvedPdfParseModel(
                    runtime_model=runtime_model,
                    requester_name='builtin-pdf-parse',
                )
            ]
    return []


def resolve_pdf_parse_model(
    ap: app.Application,
    pdf_model_uuid: str | None = None,
) -> ResolvedPdfParseModel | None:
    models = resolve_pdf_parse_models(ap, pdf_model_uuid)
    return models[0] if models else None


def resolve_api_pdf_parse_models(
    ap: app.Application,
    pdf_model_uuid: str | None = None,
) -> list[ResolvedPdfParseModel]:
    return [
        resolved
        for resolved in resolve_pdf_parse_models(ap, pdf_model_uuid)
        if resolved.requester_name != 'builtin-pdf-parse'
        and bool(resolved.runtime_model.provider.provider_entity.api_keys or [])
    ]


async def invoke_pdf_parse(
    resolved: ResolvedPdfParseModel,
    filename: str,
    content: bytes,
    extra_args: dict[str, Any] | None = None,
) -> str:
    return await resolved.runtime_model.provider.invoke_pdf_parse(
        model=resolved.runtime_model,
        filename=filename,
        content=content,
        extra_args=extra_args or {},
    )


async def extract_document_text(
    ap: app.Application,
    filename: str,
    content: bytes,
    *,
    pdf_model_uuid: str | None = None,
) -> str:
    api_providers = resolve_api_pdf_parse_models(ap, pdf_model_uuid)
    if api_providers:
        logger = getattr(ap, 'logger', None)
        for resolved in api_providers:
            try:
                ocr_text = await invoke_pdf_parse(resolved, filename, content)
                if ocr_text.strip():
                    if logger is not None:
                        logger.info(
                            'Extracted text via OCR provider %s for %s',
                            resolved.requester_name,
                            filename,
                        )
                    return ocr_text
            except Exception as exc:
                if logger is not None:
                    logger.warning(
                        'OCR provider %s extraction failed for %s: %s',
                        resolved.requester_name,
                        filename,
                        exc,
                    )

    return extract_text_from_bytes(filename, content)
