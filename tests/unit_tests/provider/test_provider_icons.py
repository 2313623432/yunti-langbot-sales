from __future__ import annotations

from langbot.pkg.provider.modelmgr import provider_icons


def test_builtin_provider_icon_paths():
    assert provider_icons.get_builtin_provider_icon_resource_path('lnv-openai') == (
        'pkg/provider/modelmgr/icons/openai.svg'
    )
    assert provider_icons.get_builtin_provider_icon_resource_path('lnv-minimax') == (
        'pkg/provider/modelmgr/icons/minimax.svg'
    )
    assert provider_icons.get_builtin_provider_icon_resource_path('lna-doubao') == (
        'pkg/provider/modelmgr/icons/doubao.svg'
    )
    assert provider_icons.get_builtin_provider_icon_resource_path('unknown') is None


def test_read_builtin_provider_icon_bytes():
    icon_bytes = provider_icons.read_builtin_provider_icon_bytes('lnv-qwen')
    assert icon_bytes is not None
    assert icon_bytes.startswith(b'<svg')
    doubao_icon_bytes = provider_icons.read_builtin_provider_icon_bytes('lna-doubao')
    assert doubao_icon_bytes is not None
    assert doubao_icon_bytes.startswith(b'<svg')
