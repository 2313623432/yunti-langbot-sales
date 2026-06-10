from __future__ import annotations

from langbot.pkg.utils import importutil

ICON_RESOURCE_DIR = 'pkg/provider/modelmgr/icons'

# Built-in provider UUID -> icon filename under ICON_RESOURCE_DIR.
BUILTIN_PROVIDER_ICON_FILES: dict[str, str] = {
    # Text
    'lnp-openai': 'openai.svg',
    'lnp-claude': 'anthropic.svg',
    'lnp-gemini': 'google.svg',
    'lnp-zhipu': 'zhipu.svg',
    'lnp-qwen': 'qwen.svg',
    'lnp-deepseek': 'deepseek.svg',
    'lnp-moonshot': 'moonshot.svg',
    'lnp-minimax': 'minimax.svg',
    'lnp-siliconflow': 'siliconflow.svg',
    'lnp-doubao': 'doubao.svg',
    'lnp-xai': 'xai.svg',
    # TTS
    'lnv-openai': 'openai.svg',
    'lnv-azure': 'azure.svg',
    'lnv-zhipu': 'zhipu.svg',
    'lnv-qwen': 'qwen.svg',
    'lnv-minimax': 'minimax.svg',
    'lnv-doubao': 'doubao.svg',
    'lnv-elevenlabs': 'elevenlabs.svg',
    'lnv-browser': 'browser.svg',
    # Embedding
    'lne-openai': 'openai.svg',
    'lne-zhipu': 'zhipu.svg',
    'lne-qwen': 'qwen.svg',
    'lne-deepseek': 'deepseek.svg',
    'lne-siliconflow': 'siliconflow.svg',
    'lne-baidu-aistudio-embedding-provider': 'baidu.svg',
    # PDF
    'lno-unpdf': 'browser.svg',
    'lno-mineru-cloud': 'qwen.svg',
    'lno-paddleocr': 'baidu.svg',
}


def get_builtin_provider_icon_resource_path(provider_uuid: str | None) -> str | None:
    if not provider_uuid:
        return None
    icon_file = BUILTIN_PROVIDER_ICON_FILES.get(provider_uuid)
    if icon_file is None:
        return None
    return f'{ICON_RESOURCE_DIR}/{icon_file}'


def read_builtin_provider_icon_bytes(provider_uuid: str) -> bytes | None:
    resource_path = get_builtin_provider_icon_resource_path(provider_uuid)
    if resource_path is None:
        return None
    try:
        return importutil.read_resource_file_bytes(resource_path)
    except FileNotFoundError:
        return None
