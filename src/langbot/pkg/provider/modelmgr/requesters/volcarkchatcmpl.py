from __future__ import annotations

import typing
import openai

from . import chatcmpl


class VolcArkChatCompletions(chatcmpl.OpenAIChatCompletions):
    """火山方舟大模型平台 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'timeout': 120,
    }

    def _prepare_extra_body(self, extra_body: dict | None = None) -> dict:
        prepared = super()._prepare_extra_body(extra_body)
        prepared.setdefault('thinking', {'type': 'disabled'})
        prepared.setdefault('reasoning_effort', 'minimal')
        return prepared
