from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.rag.knowledge import mineru_cloud


@pytest.mark.asyncio
async def test_extract_text_with_mineru_cloud_returns_markdown(monkeypatch):
    markdown_zip = io.BytesIO()
    with zipfile.ZipFile(markdown_zip, 'w') as archive:
        archive.writestr('demo/full.md', '# MinerU\n\nparsed text')

    class FakeResponse:
        def __init__(self, status: int, payload: dict | None = None, raw: bytes = b''):
            self.status = status
            self._payload = payload or {}
            self._raw = raw

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return self._payload

        async def text(self):
            return str(self._payload)

        async def read(self):
            return self._raw

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self._polls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, url, **kwargs):
            return FakeResponse(
                200,
                {
                    'code': 0,
                    'data': {
                        'batch_id': 'batch-1',
                        'file_urls': ['https://upload.example/file'],
                    },
                },
            )

        def put(self, url, **kwargs):
            return FakeResponse(200)

        def get(self, url, **kwargs):
            if 'extract-results' in url:
                self._polls += 1
                return FakeResponse(
                    200,
                    {
                        'code': 0,
                        'data': {
                            'extract_result': [
                                {
                                    'state': 'done',
                                    'full_zip_url': 'https://cdn.example/result.zip',
                                }
                            ]
                        },
                    },
                )
            return FakeResponse(200, raw=markdown_zip.getvalue())

    monkeypatch.setattr(mineru_cloud.aiohttp, 'ClientSession', lambda **kwargs: FakeSession())
    text = await mineru_cloud.extract_text_with_mineru_cloud(
        'scan.pdf',
        b'%PDF',
        token='token',
        poll_interval=0,
    )
    assert 'parsed text' in text
