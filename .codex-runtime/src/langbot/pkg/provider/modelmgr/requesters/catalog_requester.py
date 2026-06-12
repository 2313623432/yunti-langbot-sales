from __future__ import annotations

import typing

from langbot.pkg.rag.knowledge import document_text
from langbot.pkg.rag.knowledge import mineru_cloud
from langbot.pkg.rag.knowledge import paddleocr_vl

from .. import requester
from .. import tts_invoke


class _CatalogStubRequester(requester.ProviderAPIRequester):
    """Minimal requester used by built-in provider catalogs."""

    default_config: dict[str, typing.Any] = {
        'base_url': '',
        'timeout': 120,
    }

    async def invoke_llm(
        self,
        query,
        model: requester.RuntimeLLMModel,
        messages: typing.List,
        funcs: typing.List = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ):
        raise NotImplementedError(f'{self.__class__.__name__} does not support LLM inference')

    async def invoke_embedding(
        self,
        model: requester.RuntimeEmbeddingModel,
        input_text: typing.List[str],
        extra_args: dict[str, typing.Any] = {},
    ) -> typing.List[typing.List[float]]:
        raise NotImplementedError(f'{self.__class__.__name__} does not support embedding inference')


class _TTSRequesterMixin(_CatalogStubRequester):
    tts_requester: str = ''
    tts_provider: str = ''

    async def invoke_tts(
        self,
        *,
        text: str,
        model_name: str,
        api_keys: list[str] | None = None,
        extra_args: dict[str, typing.Any] | None = None,
    ) -> str | None:
        merged_extra_args = extra_args if isinstance(extra_args, dict) else {}
        voice_config = tts_invoke.apply_provider_api_keys(
            {
                'requester': self.tts_requester or self.name,
                'provider': merged_extra_args.get('provider') or self.tts_provider,
                'model': model_name,
                'base_url': self.requester_cfg.get('base_url', ''),
                **merged_extra_args,
            },
            requester=self.tts_requester or self.name or '',
            api_keys=api_keys,
        )
        config = tts_invoke.build_tts_invoke_config(voice_config, text)
        return await tts_invoke.invoke_tts(config, logger=self.ap.logger)


class AzureTTSRequester(_TTSRequesterMixin):
    tts_requester = 'azure-tts'
    tts_provider = 'azure'


class VolcengineTTSRequester(_TTSRequesterMixin):
    tts_requester = 'volcengine-tts'
    tts_provider = 'volcengine'


class ElevenLabsTTSRequester(_TTSRequesterMixin):
    tts_requester = 'elevenlabs-tts'
    tts_provider = 'elevenlabs'


class BuiltinPdfParseRequester(_CatalogStubRequester):
    async def invoke_pdf_parse(
        self,
        model: requester.RuntimeLLMModel,
        filename: str,
        content: bytes,
        extra_args: dict[str, typing.Any] | None = None,
    ) -> str:
        _ = model, extra_args
        return document_text.extract_text_from_bytes(filename, content)


class MinerUCloudRequester(_CatalogStubRequester):
    async def invoke_pdf_parse(
        self,
        model: requester.RuntimeLLMModel,
        filename: str,
        content: bytes,
        extra_args: dict[str, typing.Any] | None = None,
    ) -> str:
        merged_extra_args = dict(model.model_entity.extra_args or {})
        if extra_args:
            merged_extra_args.update(extra_args)
        provider_entity = model.provider.provider_entity
        token = model.provider.token_mgr.get_token()
        base_url = str(provider_entity.base_url or self.requester_cfg.get('base_url') or '').strip()
        timeout_seconds = float(self.requester_cfg.get('timeout') or 600)
        return await mineru_cloud.extract_text_with_mineru_cloud(
            filename,
            content,
            token=token,
            base_url=base_url,
            model_version=str(merged_extra_args.get('model_version') or 'vlm'),
            is_ocr=bool(merged_extra_args.get('is_ocr', False)),
            page_range=str(merged_extra_args.get('page_range') or merged_extra_args.get('page_ranges') or ''),
            max_wait=timeout_seconds,
        )


class PaddleOcrVlRequester(_CatalogStubRequester):
    async def invoke_pdf_parse(
        self,
        model: requester.RuntimeLLMModel,
        filename: str,
        content: bytes,
        extra_args: dict[str, typing.Any] | None = None,
    ) -> str:
        merged_extra_args = dict(model.model_entity.extra_args or {})
        if extra_args:
            merged_extra_args.update(extra_args)
        provider_entity = model.provider.provider_entity
        token = model.provider.token_mgr.get_token()
        config = paddleocr_vl.resolve_paddleocr_config(provider_entity, merged_extra_args)
        timeout_seconds = float(self.requester_cfg.get('timeout') or 600)
        return await paddleocr_vl.extract_text_with_paddleocr_vl(
            filename,
            content,
            token=token or config.token,
            model=config.model,
            job_url=config.job_url,
            provider_entity=provider_entity,
            extra_args=merged_extra_args,
            max_wait=timeout_seconds,
        )
