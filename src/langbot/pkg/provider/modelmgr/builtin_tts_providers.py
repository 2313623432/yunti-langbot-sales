from __future__ import annotations

from dataclasses import dataclass

from langbot.pkg.provider.modelmgr.builtin_protocol import ProtocolType


@dataclass(frozen=True)
class BuiltinTTSModelSpec:
    uuid: str
    model_id: str
    display_name: str
    extra_args: tuple[tuple[str, object], ...] = ()

    def to_extra_args(self) -> dict:
        payload = {'display_name': self.display_name}
        payload.update(dict(self.extra_args))
        return payload


@dataclass(frozen=True)
class BuiltinTTSProviderSpec:
    uuid: str
    name: str
    requester: str
    base_url: str
    protocol: ProtocolType
    api_key_required: bool
    sort_order: int
    models: tuple[BuiltinTTSModelSpec, ...]
    required_api_key_count: int = 1
    provider_kind: str = 'tts'


def _model(
    provider_slug: str,
    model_slug: str,
    model_id: str,
    display_name: str,
    **extra_args: object,
) -> BuiltinTTSModelSpec:
    return BuiltinTTSModelSpec(
        uuid=f'lnv-{provider_slug}-{model_slug}',
        model_id=model_id,
        display_name=display_name,
        extra_args=tuple(extra_args.items()),
    )


BUILTIN_TTS_PROVIDER_SPECS: tuple[BuiltinTTSProviderSpec, ...] = (
    BuiltinTTSProviderSpec(
        uuid='lnv-openai',
        name='OpenAI TTS',
        requester='openai-chat-completions',
        base_url='https://api.openai.com/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=10,
        models=(
            _model('openai', 'gpt-4o-mini-tts', 'gpt-4o-mini-tts', 'GPT-4o Mini TTS'),
            _model('openai', 'tts-1', 'tts-1', 'TTS-1'),
            _model('openai', 'tts-1-hd', 'tts-1-hd', 'TTS-1 HD'),
        ),
    ),
    BuiltinTTSProviderSpec(
        uuid='lnv-azure',
        name='Azure TTS',
        requester='azure-tts',
        base_url='https://eastus.tts.speech.microsoft.com',
        protocol='openai',
        api_key_required=True,
        sort_order=20,
        models=(
            _model('azure', 'neural', 'azure-neural', 'Azure Neural TTS', voice='zh-CN-XiaoxiaoNeural'),
        ),
    ),
    BuiltinTTSProviderSpec(
        uuid='lnv-zhipu',
        name='智谱 GLM TTS',
        requester='zhipuai-chat-completions',
        base_url='https://open.bigmodel.cn/api/paas/v4',
        protocol='openai',
        api_key_required=True,
        sort_order=30,
        models=(
            _model('zhipu', 'glm-tts', 'glm-tts', 'GLM TTS'),
        ),
    ),
    BuiltinTTSProviderSpec(
        uuid='lnv-qwen',
        name='通义千问 TTS',
        requester='bailian-chat-completions',
        base_url='https://dashscope.aliyuncs.com/api/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=40,
        models=(
            _model('qwen', 'qwen3-tts-flash', 'qwen3-tts-flash', 'Qwen3 TTS Flash', provider='dashscope-tts'),
            _model('qwen', 'qwen3-tts-instruct-flash', 'qwen3-tts-instruct-flash', 'Qwen3 TTS Instruct Flash', provider='dashscope-tts'),
            _model('qwen', 'qwen-tts', 'qwen-tts', 'Qwen TTS', provider='dashscope-tts'),
        ),
    ),
    BuiltinTTSProviderSpec(
        uuid='lnv-minimax',
        name='MiniMax TTS',
        requester='openai-chat-completions',
        base_url='https://api.minimaxi.com',
        protocol='claude',
        api_key_required=True,
        sort_order=50,
        models=(
            _model('minimax', 'speech-2-8-hd', 'speech-2.8-hd', 'Speech 2.8 HD'),
            _model('minimax', 'speech-2-8-turbo', 'speech-2.8-turbo', 'Speech 2.8 Turbo'),
            _model('minimax', 'speech-2-6-hd', 'speech-2.6-hd', 'Speech 2.6 HD'),
            _model('minimax', 'speech-2-6-turbo', 'speech-2.6-turbo', 'Speech 2.6 Turbo'),
            _model('minimax', 'speech-02-hd', 'speech-02-hd', 'Speech 02 HD'),
            _model('minimax', 'speech-02-turbo', 'speech-02-turbo', 'Speech 02 Turbo'),
        ),
    ),
    BuiltinTTSProviderSpec(
        uuid='lnv-doubao',
        name='豆包 TTS 2.0',
        requester='volcengine-tts',
        base_url='https://openspeech.bytedance.com',
        protocol='openai',
        api_key_required=True,
        required_api_key_count=2,
        sort_order=60,
        models=(
            _model(
                'doubao',
                'default',
                'volcano_tts',
                '豆包 TTS 2.0',
                provider='volcengine',
                cluster='volcano_tts',
                voice_type='zh_female_shuangkuaisisi_moon_bigtts',
            ),
        ),
    ),
    BuiltinTTSProviderSpec(
        uuid='lnv-elevenlabs',
        name='ElevenLabs TTS',
        requester='elevenlabs-tts',
        base_url='https://api.elevenlabs.io/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=70,
        models=(
            _model('elevenlabs', 'multilingual-v2', 'multilingual_v2', 'Multilingual v2'),
            _model('elevenlabs', 'flash-v2-5', 'flash_v2_5', 'Flash v2.5'),
            _model('elevenlabs', 'flash-v2', 'flash_v2', 'Flash v2'),
        ),
    ),
)

BUILTIN_TTS_PROVIDER_UUIDS = frozenset(spec.uuid for spec in BUILTIN_TTS_PROVIDER_SPECS)
BUILTIN_TTS_MODEL_UUIDS = frozenset(
    model.uuid for spec in BUILTIN_TTS_PROVIDER_SPECS for model in spec.models
)

_BUILTIN_PROVIDER_BY_UUID = {spec.uuid: spec for spec in BUILTIN_TTS_PROVIDER_SPECS}


def is_builtin_tts_provider(provider_uuid: str | None) -> bool:
    return provider_uuid in BUILTIN_TTS_PROVIDER_UUIDS


def get_builtin_tts_provider_spec(provider_uuid: str) -> BuiltinTTSProviderSpec | None:
    return _BUILTIN_PROVIDER_BY_UUID.get(provider_uuid)


def get_builtin_tts_catalog() -> list[dict]:
    catalog: list[dict] = []
    for spec in BUILTIN_TTS_PROVIDER_SPECS:
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
                        'abilities': ['tts'],
                        'extra_args': model.to_extra_args(),
                    }
                    for model in spec.models
                ],
            }
        )
    return catalog
