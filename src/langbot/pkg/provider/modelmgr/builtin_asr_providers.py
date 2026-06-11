from __future__ import annotations

from dataclasses import dataclass

from langbot.pkg.provider.modelmgr.builtin_protocol import ProtocolType


@dataclass(frozen=True)
class BuiltinASRModelSpec:
    uuid: str
    model_id: str
    display_name: str
    extra_args: tuple[tuple[str, object], ...] = ()

    def to_extra_args(self) -> dict:
        payload = {'display_name': self.display_name}
        payload.update(dict(self.extra_args))
        return payload


@dataclass(frozen=True)
class BuiltinASRProviderSpec:
    uuid: str
    name: str
    requester: str
    base_url: str
    protocol: ProtocolType
    api_key_required: bool
    sort_order: int
    models: tuple[BuiltinASRModelSpec, ...]
    required_api_key_count: int = 1
    provider_kind: str = 'asr'


def _model(
    provider_slug: str,
    model_slug: str,
    model_id: str,
    display_name: str,
    **extra_args: object,
) -> BuiltinASRModelSpec:
    return BuiltinASRModelSpec(
        uuid=f'lna-{provider_slug}-{model_slug}',
        model_id=model_id,
        display_name=display_name,
        extra_args=tuple(extra_args.items()),
    )


BUILTIN_ASR_PROVIDER_SPECS: tuple[BuiltinASRProviderSpec, ...] = (
    BuiltinASRProviderSpec(
        uuid='lna-qwen',
        name='通义千问 ASR',
        requester='bailian-chat-completions',
        base_url='https://dashscope.aliyuncs.com/api/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=10,
        models=(
            _model(
                'qwen',
                'qwen3-asr-flash',
                'qwen3-asr-flash',
                'Qwen3 ASR Flash',
                provider='dashscope-asr',
                language_type='Chinese',
            ),
            _model(
                'qwen',
                'qwen3-asr-flash-filetrans',
                'qwen3-asr-flash-filetrans',
                'Qwen3 ASR Flash Filetrans',
                provider='dashscope-asr',
                language_type='Chinese',
            ),
        ),
    ),
    BuiltinASRProviderSpec(
        uuid='lna-openai',
        name='OpenAI ASR',
        requester='openai-chat-completions',
        base_url='https://api.openai.com/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=20,
        models=(
            _model(
                'openai',
                'whisper-1',
                'whisper-1',
                'Whisper 1',
                provider='openai-asr',
            ),
        ),
    ),
    BuiltinASRProviderSpec(
        uuid='lna-doubao',
        name='豆包语音 ASR',
        requester='volcengine-asr',
        base_url='https://openspeech.bytedance.com',
        protocol='openai',
        api_key_required=True,
        sort_order=30,
        models=(
            _model(
                'doubao',
                'bigasr-flash',
                'bigmodel',
                '豆包语音录音文件识别极速版',
                provider='volcengine-asr',
                language_type='zh-CN',
                resource_id='volc.bigasr.auc_turbo',
            ),
        ),
    ),
)

BUILTIN_ASR_PROVIDER_UUIDS = frozenset(spec.uuid for spec in BUILTIN_ASR_PROVIDER_SPECS)
BUILTIN_ASR_MODEL_UUIDS = frozenset(
    model.uuid for spec in BUILTIN_ASR_PROVIDER_SPECS for model in spec.models
)

_BUILTIN_PROVIDER_BY_UUID = {spec.uuid: spec for spec in BUILTIN_ASR_PROVIDER_SPECS}


def is_builtin_asr_provider(provider_uuid: str | None) -> bool:
    return provider_uuid in BUILTIN_ASR_PROVIDER_UUIDS


def get_builtin_asr_provider_spec(provider_uuid: str) -> BuiltinASRProviderSpec | None:
    return _BUILTIN_PROVIDER_BY_UUID.get(provider_uuid)


def get_builtin_asr_catalog() -> list[dict]:
    catalog: list[dict] = []
    for spec in BUILTIN_ASR_PROVIDER_SPECS:
        catalog.append(
            {
                'uuid': spec.uuid,
                'name': spec.name,
                'requester': spec.requester,
                'base_url': spec.base_url,
                'protocol': spec.protocol,
                'api_key_required': spec.api_key_required,
                'required_api_key_count': spec.required_api_key_count,
                'sort_order': spec.sort_order,
                'provider_kind': spec.provider_kind,
                'models': [
                    {
                        'uuid': model.uuid,
                        'model_id': model.model_id,
                        'display_name': model.display_name,
                        'abilities': ['asr'],
                        'extra_args': model.to_extra_args(),
                    }
                    for model in spec.models
                ],
            }
        )
    return catalog
