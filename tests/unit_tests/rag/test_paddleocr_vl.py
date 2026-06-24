from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, patch

from langbot.pkg.rag.knowledge import paddleocr_vl


def test_parse_jsonl_markdown_extracts_layout_text():
    payload = {
        'result': {
            'layoutParsingResults': [
                {'markdown': {'text': '# 第一页\n\n销售话术'}},
                {'markdown': {'text': '## 第二页\n\nFAQ'}},
            ]
        }
    }
    jsonl_text = json.dumps(payload)
    text = paddleocr_vl.parse_jsonl_markdown(jsonl_text)
    assert '销售话术' in text
    assert 'FAQ' in text


@pytest.mark.asyncio
async def test_extract_text_with_paddleocr_vl_returns_parsed_markdown():
    captured_request = {}
    jsonl_payload = json.dumps(
        {
            'result': {
                'layoutParsingResults': [{'markdown': {'text': 'OCR 提取内容'}}],
            }
        }
    )

    class FakeResponse:
        def __init__(self, status: int, payload: dict | None = None, text_value: str = ''):
            self.status = status
            self._payload = payload or {}
            self._text_value = text_value

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return self._payload

        async def text(self):
            return self._text_value

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self._get_calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            captured_request['args'] = args
            captured_request['kwargs'] = kwargs
            return FakeResponse(200, {'data': {'jobId': 'job-1'}})

        def get(self, url, **kwargs):
            self._get_calls += 1
            if url.endswith('/job-1'):
                return FakeResponse(200, {'data': {'state': 'done', 'resultUrl': {'jsonUrl': 'https://json'}}})
            return FakeResponse(200, text_value=jsonl_payload)

    with patch('langbot.pkg.rag.knowledge.paddleocr_vl.aiohttp.ClientSession', return_value=FakeSession()):
        text = await paddleocr_vl.extract_text_with_paddleocr_vl(
            'scan.pdf',
            b'%PDF-1.4',
            token='test-token',
            job_url='https://paddleocr.aistudio-app.com/api/v2/ocr/jobs',
        )
    assert text == 'OCR 提取内容'
    assert captured_request['args'][0] == 'https://paddleocr.aistudio-app.com/api/v2/ocr/jobs'
    assert captured_request['kwargs']['headers']['Authorization'] == 'bearer test-token'
    assert 'data' in captured_request['kwargs']
