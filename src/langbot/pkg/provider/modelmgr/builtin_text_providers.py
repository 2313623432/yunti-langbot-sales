from __future__ import annotations

from dataclasses import dataclass
from langbot.pkg.provider.modelmgr import builtin_provider_common
from langbot.pkg.provider.modelmgr.builtin_protocol import ProtocolType


@dataclass(frozen=True)
class BuiltinTextModelSpec:
    uuid: str
    model_id: str
    display_name: str
    abilities: tuple[str, ...]
    context_window: int
    max_output_tokens: int
    streaming: bool = True

    def to_extra_args(self) -> dict:
        return {
            'display_name': self.display_name,
            'context_window': self.context_window,
            'max_output_tokens': self.max_output_tokens,
            'streaming': self.streaming,
        }


@dataclass(frozen=True)
class BuiltinTextProviderSpec:
    uuid: str
    name: str
    requester: str
    base_url: str
    protocol: ProtocolType
    api_key_required: bool
    sort_order: int
    models: tuple[BuiltinTextModelSpec, ...]


def _model(
    provider_slug: str,
    model_slug: str,
    model_id: str,
    display_name: str,
    *,
    abilities: tuple[str, ...] = ('func_call',),
    context_window: int = 128_000,
    max_output_tokens: int = 16_384,
    streaming: bool = True,
) -> BuiltinTextModelSpec:
    return BuiltinTextModelSpec(
        uuid=f'lnp-{provider_slug}-{model_slug}',
        model_id=model_id,
        display_name=display_name,
        abilities=abilities,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        streaming=streaming,
    )


BUILTIN_TEXT_PROVIDER_SPECS: tuple[BuiltinTextProviderSpec, ...] = (
    BuiltinTextProviderSpec(
        uuid='lnp-openai',
        name='OpenAI',
        requester='openai-chat-completions',
        base_url='https://api.openai.com/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=10,
        models=(
            _model('openai', 'gpt-5-4', 'gpt-5.4', 'GPT-5.4', abilities=('vision', 'func_call'), context_window=256_000),
            _model('openai', 'gpt-5-4-mini', 'gpt-5.4-mini', 'GPT-5.4 Mini', abilities=('vision', 'func_call')),
            _model('openai', 'gpt-5-4-nano', 'gpt-5.4-nano', 'GPT-5.4 Nano', abilities=('func_call',), max_output_tokens=8192),
            _model('openai', 'gpt-5-2', 'gpt-5.2', 'GPT-5.2', abilities=('vision', 'func_call'), context_window=256_000),
            _model('openai', 'gpt-5-1', 'gpt-5.1', 'GPT-5.1', abilities=('vision', 'func_call')),
            _model('openai', 'gpt-4o', 'gpt-4o', 'GPT-4o', abilities=('vision', 'func_call')),
            _model('openai', 'gpt-4o-mini', 'gpt-4o-mini', 'GPT-4o Mini', abilities=('vision', 'func_call')),
            _model('openai', 'gpt-3-5-turbo', 'gpt-3.5-turbo', 'GPT-3.5 Turbo', abilities=('func_call',), context_window=16_385, max_output_tokens=4096),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-claude',
        name='Claude',
        requester='anthropic-messages',
        base_url='https://api.anthropic.com',
        protocol='claude',
        api_key_required=True,
        sort_order=20,
        models=(
            _model('claude', 'opus-4-6', 'claude-opus-4-6', 'Claude Opus 4.6', abilities=('vision', 'func_call'), context_window=200_000),
            _model('claude', 'sonnet-4-6', 'claude-sonnet-4-6', 'Claude Sonnet 4.6', abilities=('vision', 'func_call'), context_window=200_000),
            _model('claude', 'sonnet-4-5', 'claude-sonnet-4-5', 'Claude Sonnet 4.5', abilities=('vision', 'func_call'), context_window=200_000),
            _model('claude', 'haiku-4-5', 'claude-haiku-4-5', 'Claude Haiku 4.5', abilities=('vision', 'func_call'), context_window=200_000, max_output_tokens=8192),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-gemini',
        name='Gemini',
        requester='gemini-chat-completions',
        base_url='https://generativelanguage.googleapis.com/v1beta/openai',
        protocol='gemini',
        api_key_required=True,
        sort_order=30,
        models=(
            _model('gemini', '2-5-pro', 'gemini-2.5-pro', 'Gemini 2.5 Pro', abilities=('vision', 'func_call'), context_window=1_048_576),
            _model('gemini', '2-5-flash', 'gemini-2.5-flash', 'Gemini 2.5 Flash', abilities=('vision', 'func_call'), context_window=1_048_576),
            _model('gemini', '2-0-flash', 'gemini-2.0-flash', 'Gemini 2.0 Flash', abilities=('vision', 'func_call')),
            _model('gemini', '2-0-flash-lite', 'gemini-2.0-flash-lite', 'Gemini 2.0 Flash Lite', abilities=('func_call',), max_output_tokens=8192),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-zhipu',
        name='智谱 GLM',
        requester='zhipuai-chat-completions',
        base_url='https://open.bigmodel.cn/api/paas/v4',
        protocol='openai',
        api_key_required=True,
        sort_order=40,
        models=(
            _model('zhipu', 'glm-4', 'glm-4', 'GLM-4', abilities=('vision', 'func_call')),
            _model('zhipu', 'glm-4-7', 'glm-4.7', 'GLM-4.7', abilities=('vision', 'func_call')),
            _model('zhipu', 'glm-4-7-flashx', 'glm-4.7-flashx', 'GLM-4.7 FlashX', abilities=('func_call',)),
            _model('zhipu', 'glm-4-7-flash', 'glm-4.7-flash', 'GLM-4.7 Flash', abilities=('func_call',)),
            _model('zhipu', 'glm-4-6', 'glm-4.6', 'GLM-4.6', abilities=('vision', 'func_call')),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-qwen',
        name='通义千问',
        requester='bailian-chat-completions',
        base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=50,
        models=(
            _model('qwen', 'qwen-max', 'qwen-max', 'Qwen Max', abilities=('vision', 'func_call')),
            _model('qwen', 'qwen-plus', 'qwen-plus', 'Qwen Plus', abilities=('vision', 'func_call')),
            _model('qwen', 'qwen-turbo', 'qwen-turbo', 'Qwen Turbo', abilities=('func_call',)),
            _model('qwen', 'qwen-vl-max', 'qwen-vl-max', 'Qwen VL Max', abilities=('vision', 'func_call')),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-deepseek',
        name='DeepSeek',
        requester='deepseek-chat-completions',
        base_url='https://api.deepseek.com',
        protocol='openai',
        api_key_required=True,
        sort_order=60,
        models=(
            _model('deepseek', 'deepseek-chat', 'deepseek-chat', 'DeepSeek Chat', abilities=('func_call',), context_window=64_000),
            _model('deepseek', 'deepseek-reasoner', 'deepseek-reasoner', 'DeepSeek Reasoner', abilities=('func_call',), context_window=64_000),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-moonshot',
        name='Kimi (Moonshot)',
        requester='moonshot-chat-completions',
        base_url='https://api.moonshot.ai/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=70,
        models=(
            _model('moonshot', 'kimi-k2', 'kimi-k2', 'Kimi K2', abilities=('vision', 'func_call'), context_window=256_000),
            _model('moonshot', 'moonshot-v1-128k', 'moonshot-v1-128k', 'Moonshot v1 128K', abilities=('func_call',), context_window=128_000),
            _model('moonshot', 'moonshot-v1-32k', 'moonshot-v1-32k', 'Moonshot v1 32K', abilities=('func_call',), context_window=32_768),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-minimax',
        name='MiniMax',
        requester='openai-chat-completions',
        base_url='https://api.minimax.chat/v1',
        protocol='claude',
        api_key_required=True,
        sort_order=80,
        models=(
            _model('minimax', 'abab6-5s-chat', 'abab6.5s-chat', 'MiniMax abab6.5s', abilities=('func_call',)),
            _model('minimax', 'minimax-text-01', 'MiniMax-Text-01', 'MiniMax Text 01', abilities=('func_call',)),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-siliconflow',
        name='硅基流动',
        requester='siliconflow-chat-completions',
        base_url='https://api.siliconflow.cn/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=90,
        models=(
            _model('siliconflow', 'deepseek-v3', 'deepseek-ai/DeepSeek-V3', 'DeepSeek V3', abilities=('func_call',)),
            _model('siliconflow', 'qwen2-5-72b', 'Qwen/Qwen2.5-72B-Instruct', 'Qwen2.5 72B', abilities=('func_call',)),
            _model('siliconflow', 'glm-4-9b', 'THUDM/glm-4-9b-chat', 'GLM-4 9B', abilities=('func_call',)),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-doubao',
        name='豆包',
        requester='volcark-chat-completions',
        base_url='https://ark.cn-beijing.volces.com/api/v3',
        protocol='openai',
        api_key_required=True,
        sort_order=100,
        models=(
            _model('doubao', 'doubao-pro-32k', 'doubao-pro-32k', 'Doubao Pro 32K', abilities=('func_call',), context_window=32_768),
            _model('doubao', 'doubao-lite-32k', 'doubao-lite-32k', 'Doubao Lite 32K', abilities=('func_call',), context_window=32_768),
            _model('doubao', 'doubao-pro-128k', 'doubao-pro-128k', 'Doubao Pro 128K', abilities=('func_call',), context_window=128_000),
        ),
    ),
    BuiltinTextProviderSpec(
        uuid='lnp-xai',
        name='Grok (xAI)',
        requester='xai-chat-completions',
        base_url='https://api.x.ai/v1',
        protocol='openai',
        api_key_required=True,
        sort_order=110,
        models=(
            _model('xai', 'grok-3', 'grok-3', 'Grok 3', abilities=('vision', 'func_call'), context_window=131_072),
            _model('xai', 'grok-3-mini', 'grok-3-mini', 'Grok 3 Mini', abilities=('func_call',)),
        ),
    ),
)

BUILTIN_TEXT_PROVIDER_UUIDS = frozenset(spec.uuid for spec in BUILTIN_TEXT_PROVIDER_SPECS)
BUILTIN_TEXT_MODEL_UUIDS = frozenset(
    model.uuid for spec in BUILTIN_TEXT_PROVIDER_SPECS for model in spec.models
)
NO_API_KEY_REQUESTERS = builtin_provider_common.NO_API_KEY_REQUESTERS

_BUILTIN_PROVIDER_BY_UUID = {spec.uuid: spec for spec in BUILTIN_TEXT_PROVIDER_SPECS}


def is_builtin_text_provider(provider_uuid: str | None) -> bool:
    return provider_uuid in BUILTIN_TEXT_PROVIDER_UUIDS


def get_builtin_text_provider_spec(provider_uuid: str) -> BuiltinTextProviderSpec | None:
    return _BUILTIN_PROVIDER_BY_UUID.get(provider_uuid)


def provider_requires_api_key(provider_dict: dict) -> bool:
    return builtin_provider_common.provider_requires_api_key(enrich_provider_dict(provider_dict))


def is_provider_configured(provider_dict: dict, *, model_count: int = 1) -> bool:
    from langbot.pkg.provider.modelmgr import builtin_registry

    return builtin_registry.is_provider_configured(provider_dict, model_count=model_count)


def enrich_provider_dict(provider_dict: dict) -> dict:
    from langbot.pkg.provider.modelmgr import builtin_registry

    return builtin_registry.enrich_provider_dict(provider_dict)


def get_builtin_text_catalog() -> list[dict]:
    catalog: list[dict] = []
    for spec in BUILTIN_TEXT_PROVIDER_SPECS:
        catalog.append(
            {
                'uuid': spec.uuid,
                'name': spec.name,
                'requester': spec.requester,
                'base_url': spec.base_url,
                'protocol': spec.protocol,
                'api_key_required': spec.api_key_required,
                'sort_order': spec.sort_order,
                'models': [
                    {
                        'uuid': model.uuid,
                        'model_id': model.model_id,
                        'display_name': model.display_name,
                        'abilities': list(model.abilities),
                        'context_window': model.context_window,
                        'max_output_tokens': model.max_output_tokens,
                        'streaming': model.streaming,
                    }
                    for model in spec.models
                ],
            }
        )
    return catalog
