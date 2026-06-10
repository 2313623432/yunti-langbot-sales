from __future__ import annotations

from dataclasses import dataclass

from langbot.pkg.provider.modelmgr.builtin_protocol import ProtocolType


@dataclass(frozen=True)
class BuiltinEmbeddingModelSpec:
    uuid: str
    model_name: str
    display_name: str
    prefered_ranking: int = 0

    def to_extra_args(self) -> dict:
        return {'model': self.model_name, 'display_name': self.display_name}


@dataclass(frozen=True)
class BuiltinEmbeddingProviderSpec:
    uuid: str
    name: str
    requester: str
    base_url: str
    protocol: ProtocolType
    api_key_required: bool
    sort_order: int
    models: tuple[BuiltinEmbeddingModelSpec, ...]
    provider_kind: str = 'embedding'


def _model(
    provider_slug: str,
    model_slug: str,
    model_name: str,
    display_name: str,
    *,
    prefered_ranking: int = 0,
) -> BuiltinEmbeddingModelSpec:
    return BuiltinEmbeddingModelSpec(
        uuid=f'lne-{provider_slug}-{model_slug}',
        model_name=model_name,
        display_name=display_name,
        prefered_ranking=prefered_ranking,
    )


BUILTIN_EMBEDDING_PROVIDER_SPECS: tuple[BuiltinEmbeddingProviderSpec, ...] = (
    BuiltinEmbeddingProviderSpec(
        uuid='lne-openai',
        name='OpenAI Embedding',
        requester='openai-chat-completions',
        base_url='https://api.openai.com/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=10,
        models=(
            _model('openai', '3-large', 'text-embedding-3-large', 'text-embedding-3-large'),
            _model('openai', '3-small', 'text-embedding-3-small', 'text-embedding-3-small'),
            _model('openai', 'ada-002', 'text-embedding-ada-002', 'text-embedding-ada-002'),
        ),
    ),
    BuiltinEmbeddingProviderSpec(
        uuid='lne-zhipu',
        name='智谱 Embedding',
        requester='zhipuai-chat-completions',
        base_url='https://open.bigmodel.cn/api/paas/v4',
        protocol='openai',
        api_key_required=True,
        sort_order=20,
        models=(
            _model('zhipu', 'embedding-3', 'embedding-3', 'embedding-3'),
            _model('zhipu', 'embedding-2', 'embedding-2', 'embedding-2'),
        ),
    ),
    BuiltinEmbeddingProviderSpec(
        uuid='lne-qwen',
        name='通义千问 Embedding',
        requester='bailian-chat-completions',
        base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=30,
        models=(
            _model('qwen', 'v3', 'text-embedding-v3', 'text-embedding-v3', prefered_ranking=1),
            _model('qwen', 'v2', 'text-embedding-v2', 'text-embedding-v2'),
        ),
    ),
    BuiltinEmbeddingProviderSpec(
        uuid='lne-deepseek',
        name='DeepSeek Embedding',
        requester='deepseek-chat-completions',
        base_url='https://api.deepseek.com',
        protocol='openai',
        api_key_required=True,
        sort_order=40,
        models=(
            _model('deepseek', 'embedding', 'deepseek-embedding', 'deepseek-embedding'),
        ),
    ),
    BuiltinEmbeddingProviderSpec(
        uuid='lne-siliconflow',
        name='硅基流动 Embedding',
        requester='siliconflow-chat-completions',
        base_url='https://api.siliconflow.cn/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=50,
        models=(
            _model('siliconflow', 'bge-m3', 'BAAI/bge-m3', 'BGE-M3'),
            _model('siliconflow', 'bge-large-zh', 'BAAI/bge-large-zh-v1.5', 'BGE Large ZH'),
            _model('siliconflow', 'qwen3-8b', 'Qwen/Qwen3-Embedding-8B', 'Qwen3 Embedding 8B'),
        ),
    ),
    BuiltinEmbeddingProviderSpec(
        uuid='lne-ollama',
        name='Ollama Embedding',
        requester='ollama-chat',
        base_url='http://127.0.0.1:11434',
        protocol='openai',
        api_key_required=False,
        sort_order=60,
        models=(
            _model('ollama', 'nomic-embed', 'nomic-embed-text', 'nomic-embed-text'),
            _model('ollama', 'bge-m3', 'bge-m3', 'bge-m3'),
        ),
    ),
    BuiltinEmbeddingProviderSpec(
        uuid='lne-baidu-aistudio-embedding-provider',
        name='百度星河 Embedding',
        requester='openai-chat-completions',
        base_url='https://aistudio.baidu.com/llm/lmapi/v3',
        protocol='openai',
        api_key_required=True,
        sort_order=70,
        models=(
            _model(
                'baidu',
                'bge-large-zh',
                'bge-large-zh',
                '百度星河 bge-large-zh',
                prefered_ranking=0,
            ),
        ),
    ),
)

BUILTIN_EMBEDDING_PROVIDER_UUIDS = frozenset(spec.uuid for spec in BUILTIN_EMBEDDING_PROVIDER_SPECS)
BUILTIN_EMBEDDING_MODEL_UUIDS = frozenset(
    model.uuid for spec in BUILTIN_EMBEDDING_PROVIDER_SPECS for model in spec.models
)

# Keep legacy UUIDs for backward compatibility with existing deployments.
LEGACY_EMBEDDING_PROVIDER_UUIDS = frozenset({'lne-bailian-embedding-provider'})
LEGACY_EMBEDDING_MODEL_UUIDS = frozenset({'lne-default-embedding-model'})

_BUILTIN_PROVIDER_BY_UUID = {spec.uuid: spec for spec in BUILTIN_EMBEDDING_PROVIDER_SPECS}


def is_builtin_embedding_provider(provider_uuid: str | None) -> bool:
    return provider_uuid in BUILTIN_EMBEDDING_PROVIDER_UUIDS


def get_builtin_embedding_provider_spec(provider_uuid: str) -> BuiltinEmbeddingProviderSpec | None:
    return _BUILTIN_PROVIDER_BY_UUID.get(provider_uuid)


def get_builtin_embedding_catalog() -> list[dict]:
    catalog: list[dict] = []
    for spec in BUILTIN_EMBEDDING_PROVIDER_SPECS:
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
                        'name': model.display_name,
                        'model_name': model.model_name,
                        'prefered_ranking': model.prefered_ranking,
                        'extra_args': model.to_extra_args(),
                    }
                    for model in spec.models
                ],
            }
        )
    return catalog
