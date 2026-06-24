from __future__ import annotations

from dataclasses import dataclass

from langbot.pkg.provider.modelmgr.builtin_protocol import ProtocolType


@dataclass(frozen=True)
class BuiltinPdfModelSpec:
    uuid: str
    model_id: str
    display_name: str
    extra_args: tuple[tuple[str, object], ...] = ()

    def to_extra_args(self) -> dict:
        payload = {'display_name': self.display_name}
        payload.update(dict(self.extra_args))
        return payload


@dataclass(frozen=True)
class BuiltinPdfProviderSpec:
    uuid: str
    name: str
    requester: str
    base_url: str
    protocol: ProtocolType
    api_key_required: bool
    sort_order: int
    models: tuple[BuiltinPdfModelSpec, ...]
    provider_kind: str = 'pdf'


def _model(
    provider_slug: str,
    model_slug: str,
    model_id: str,
    display_name: str,
    **extra_args: object,
) -> BuiltinPdfModelSpec:
    return BuiltinPdfModelSpec(
        uuid=f'lno-{provider_slug}-{model_slug}',
        model_id=model_id,
        display_name=display_name,
        extra_args=tuple(extra_args.items()),
    )


BUILTIN_PDF_PROVIDER_SPECS: tuple[BuiltinPdfProviderSpec, ...] = (
    BuiltinPdfProviderSpec(
        uuid='lno-unpdf',
        name='内置 PDF 解析',
        requester='builtin-pdf-parse',
        base_url='local://pdf',
        protocol='openai',
        api_key_required=False,
        sort_order=10,
        models=(
            _model('unpdf', 'default', 'pypdf2', 'PyPDF2 本地解析', parser='pypdf2'),
        ),
    ),
    BuiltinPdfProviderSpec(
        uuid='lno-mineru-cloud',
        name='MinerU（云端）',
        requester='mineru-cloud',
        base_url='https://mineru.net/api/v4',
        protocol='openai',
        api_key_required=True,
        sort_order=30,
        models=(
            _model(
                'mineru-cloud',
                'vlm',
                'mineru-vlm',
                'MinerU VLM',
                model_version='vlm',
                is_ocr=True,
                page_range='',
            ),
        ),
    ),
    BuiltinPdfProviderSpec(
        uuid='lno-paddleocr',
        name='PaddleOCR-VL',
        requester='paddleocr-vl',
        base_url='https://paddleocr.aistudio-app.com/api/v2/ocr/jobs',
        protocol='openai',
        api_key_required=True,
        sort_order=40,
        models=(
            _model(
                'paddleocr',
                'vl-1-6',
                'PaddleOCR-VL-1.6',
                'PaddleOCR-VL 1.6',
                model='PaddleOCR-VL-1.6',
            ),
        ),
    ),
)

BUILTIN_PDF_PROVIDER_UUIDS = frozenset(spec.uuid for spec in BUILTIN_PDF_PROVIDER_SPECS)
BUILTIN_PDF_MODEL_UUIDS = frozenset(
    model.uuid for spec in BUILTIN_PDF_PROVIDER_SPECS for model in spec.models
)

_BUILTIN_PROVIDER_BY_UUID = {spec.uuid: spec for spec in BUILTIN_PDF_PROVIDER_SPECS}


def is_builtin_pdf_provider(provider_uuid: str | None) -> bool:
    return provider_uuid in BUILTIN_PDF_PROVIDER_UUIDS


def get_builtin_pdf_provider_spec(provider_uuid: str) -> BuiltinPdfProviderSpec | None:
    return _BUILTIN_PROVIDER_BY_UUID.get(provider_uuid)


def get_builtin_pdf_catalog() -> list[dict]:
    catalog: list[dict] = []
    for spec in BUILTIN_PDF_PROVIDER_SPECS:
        catalog.append(
            {
                'uuid': spec.uuid,
                'name': spec.name,
                'requester': spec.requester,
                'base_url': spec.base_url,
                'protocol': spec.protocol,
                'api_key_required': spec.api_key_required,
                'required_api_key_count': 0 if not spec.api_key_required else 1,
                'sort_order': spec.sort_order,
                'provider_kind': spec.provider_kind,
                'models': [
                    {
                        'uuid': model.uuid,
                        'model_id': model.model_id,
                        'display_name': model.display_name,
                        'abilities': ['pdf_parse'],
                        'extra_args': model.to_extra_args(),
                    }
                    for model in spec.models
                ],
            }
        )
    return catalog
