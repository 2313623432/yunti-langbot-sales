from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.provider.modelmgr.requesters import catalog_requester
from langbot.pkg.rag.knowledge import mineru_cloud
from langbot.pkg.rag.knowledge import pdf_parse_service
from langbot.pkg.rag.knowledge import paddleocr_vl


def test_extract_markdown_from_zip_prefers_full_md():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('demo/other.md', 'other')
        archive.writestr('demo/full.md', '# Parsed\n\ncontent')
    text = mineru_cloud.extract_markdown_from_zip(buffer.getvalue())
    assert text == '# Parsed\n\ncontent'


def test_resolve_paddleocr_config_prefers_provider_credentials():
    provider_entity = Mock(base_url='https://custom.example/ocr/jobs', api_keys=['provider-token'])
    config = paddleocr_vl.resolve_paddleocr_config(provider_entity, {'model': 'PaddleOCR-VL-1.6'})
    assert config.token == 'provider-token'
    assert config.job_url == 'https://custom.example/ocr/jobs'
    assert config.model == 'PaddleOCR-VL-1.6'


def test_resolve_pdf_parse_model_prefers_configured_api_provider():
    unpdf_provider = Mock(provider_entity=Mock(uuid='lno-unpdf', requester='builtin-pdf-parse', base_url='local://pdf', api_keys=[]))
    paddle_provider = Mock(
        provider_entity=Mock(
            uuid='lno-paddleocr',
            requester='paddleocr-vl',
            base_url='https://paddleocr.aistudio-app.com/api/v2/ocr/jobs',
            api_keys=['token'],
        )
    )
    unpdf_model = Mock(
        model_entity=Mock(uuid='lno-unpdf-default', abilities=['pdf_parse'], prefered_ranking=0, extra_args={}),
        provider=unpdf_provider,
    )
    paddle_model = Mock(
        model_entity=Mock(uuid='lno-paddleocr-vl-1-6', abilities=['pdf_parse'], prefered_ranking=0, extra_args={}),
        provider=paddle_provider,
    )
    ap = Mock(model_mgr=Mock(llm_models=[unpdf_model, paddle_model]))

    resolved = pdf_parse_service.resolve_pdf_parse_model(ap)
    assert resolved is not None
    assert resolved.requester_name == 'paddleocr-vl'


@pytest.mark.asyncio
async def test_builtin_pdf_requester_uses_local_extractor():
    requester = catalog_requester.BuiltinPdfParseRequester(Mock(), {})
    model = Mock(model_entity=Mock(extra_args={}), provider=Mock(provider_entity=Mock()))
    text = await requester.invoke_pdf_parse(model, 'note.md', b'hello world')
    assert text == 'hello world'


@pytest.mark.asyncio
async def test_paddleocr_requester_delegates_to_client(monkeypatch):
    requester = catalog_requester.PaddleOcrVlRequester(Mock(), {})
    model = Mock(
        model_entity=Mock(extra_args={'model': 'PaddleOCR-VL-1.6'}),
        provider=Mock(
            provider_entity=Mock(
                base_url='https://paddleocr.aistudio-app.com/api/v2/ocr/jobs',
                api_keys=['token'],
            ),
            token_mgr=Mock(get_token=Mock(return_value='token')),
        ),
    )
    mocked = AsyncMock(return_value='ocr text')
    monkeypatch.setattr(paddleocr_vl, 'extract_text_with_paddleocr_vl', mocked)
    text = await requester.invoke_pdf_parse(model, 'scan.pdf', b'%PDF')
    assert text == 'ocr text'


@pytest.mark.asyncio
async def test_mineru_cloud_requester_delegates_to_client(monkeypatch):
    requester = catalog_requester.MinerUCloudRequester(Mock(), {'timeout': 120})
    model = Mock(
        model_entity=Mock(extra_args={'model_version': 'vlm', 'is_ocr': True, 'page_range': '1-3'}),
        provider=Mock(
            provider_entity=Mock(base_url='https://mineru.net/api/v4', api_keys=['token']),
            token_mgr=Mock(get_token=Mock(return_value='token')),
        ),
    )
    mocked = AsyncMock(return_value='mineru markdown')
    monkeypatch.setattr(mineru_cloud, 'extract_text_with_mineru_cloud', mocked)
    text = await requester.invoke_pdf_parse(model, 'scan.pdf', b'%PDF')
    assert text == 'mineru markdown'


@pytest.mark.asyncio
async def test_extract_document_text_prefers_api_provider_even_when_local_text_exists(monkeypatch):
    provider = Mock(
        provider_entity=Mock(uuid='lno-paddleocr', requester='paddleocr-vl', base_url='https://x', api_keys=['token']),
        invoke_pdf_parse=AsyncMock(return_value='ocr result'),
    )
    runtime_model = Mock(
        model_entity=Mock(uuid='lno-paddleocr-vl-1-6', abilities=['pdf_parse'], prefered_ranking=0, extra_args={}),
        provider=provider,
    )
    ap = Mock(logger=Mock(), model_mgr=Mock(llm_models=[runtime_model]))
    monkeypatch.setattr(
        pdf_parse_service,
        'extract_text_from_bytes',
        Mock(return_value='local pdf text'),
    )

    text = await pdf_parse_service.extract_document_text(ap, 'readable.pdf', b'%PDF-local-text')
    assert text == 'ocr result'
    provider.invoke_pdf_parse.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_document_text_uses_local_pdf_when_no_api_provider(monkeypatch):
    ap = Mock(logger=Mock(), model_mgr=Mock(llm_models=[]))
    monkeypatch.setattr(
        pdf_parse_service,
        'extract_text_from_bytes',
        Mock(return_value='local pdf text'),
    )

    text = await pdf_parse_service.extract_document_text(ap, 'readable.pdf', b'%PDF-local-text')
    assert text == 'local pdf text'


@pytest.mark.asyncio
async def test_extract_document_text_falls_back_to_local_when_api_provider_returns_empty(monkeypatch):
    provider = Mock(
        provider_entity=Mock(uuid='lno-paddleocr', requester='paddleocr-vl', base_url='https://x', api_keys=['token']),
        invoke_pdf_parse=AsyncMock(return_value=''),
    )
    runtime_model = Mock(
        model_entity=Mock(uuid='lno-paddleocr-vl-1-6', abilities=['pdf_parse'], prefered_ranking=0, extra_args={}),
        provider=provider,
    )
    ap = Mock(logger=Mock(), model_mgr=Mock(llm_models=[runtime_model]))
    monkeypatch.setattr(
        pdf_parse_service,
        'extract_text_from_bytes',
        Mock(return_value='local pdf text'),
    )

    text = await pdf_parse_service.extract_document_text(ap, 'scan.pdf', b'%PDF')
    assert text == 'local pdf text'


@pytest.mark.asyncio
async def test_extract_document_text_falls_back_to_provider_when_local_empty():
    provider = Mock(
        provider_entity=Mock(uuid='lno-paddleocr', requester='paddleocr-vl', base_url='https://x', api_keys=['token']),
        invoke_pdf_parse=AsyncMock(return_value='ocr result'),
    )
    runtime_model = Mock(
        model_entity=Mock(uuid='lno-paddleocr-vl-1-6', abilities=['pdf_parse'], prefered_ranking=0, extra_args={}),
        provider=provider,
    )
    ap = Mock(logger=Mock(), model_mgr=Mock(llm_models=[runtime_model]))

    text = await pdf_parse_service.extract_document_text(ap, 'scan.pdf', b'%PDF-empty')
    assert text == 'ocr result'
    provider.invoke_pdf_parse.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_document_text_returns_local_text_without_provider_call():
    ap = Mock(logger=Mock(), model_mgr=Mock(llm_models=[]))
    text = await pdf_parse_service.extract_document_text(ap, 'note.md', b'local content')
    assert text == 'local content'


@pytest.mark.asyncio
async def test_extract_document_text_prefers_api_provider_for_markdown(monkeypatch):
    provider = Mock(
        provider_entity=Mock(uuid='lno-paddleocr', requester='paddleocr-vl', base_url='https://x', api_keys=['token']),
        invoke_pdf_parse=AsyncMock(return_value='ocr markdown'),
    )
    runtime_model = Mock(
        model_entity=Mock(uuid='lno-paddleocr-vl-1-6', abilities=['pdf_parse'], prefered_ranking=0, extra_args={}),
        provider=provider,
    )
    ap = Mock(logger=Mock(), model_mgr=Mock(llm_models=[runtime_model]))
    monkeypatch.setattr(
        pdf_parse_service,
        'extract_text_from_bytes',
        Mock(return_value='local markdown'),
    )

    text = await pdf_parse_service.extract_document_text(ap, 'note.md', b'# local')
    assert text == 'ocr markdown'
    provider.invoke_pdf_parse.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_document_text_prefers_api_provider_for_xlsx(monkeypatch):
    provider = Mock(
        provider_entity=Mock(uuid='lno-paddleocr', requester='paddleocr-vl', base_url='https://x', api_keys=['token']),
        invoke_pdf_parse=AsyncMock(return_value='ocr spreadsheet'),
    )
    runtime_model = Mock(
        model_entity=Mock(uuid='lno-paddleocr-vl-1-6', abilities=['pdf_parse'], prefered_ranking=0, extra_args={}),
        provider=provider,
    )
    ap = Mock(logger=Mock(), model_mgr=Mock(llm_models=[runtime_model]))
    monkeypatch.setattr(
        pdf_parse_service,
        'extract_text_from_bytes',
        Mock(return_value='local xlsx'),
    )

    text = await pdf_parse_service.extract_document_text(ap, 'data.xlsx', b'PK\x03\x04')
    assert text == 'ocr spreadsheet'
    provider.invoke_pdf_parse.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_document_text_prefers_api_provider_for_pptx(monkeypatch):
    provider = Mock(
        provider_entity=Mock(uuid='lno-paddleocr', requester='paddleocr-vl', base_url='https://x', api_keys=['token']),
        invoke_pdf_parse=AsyncMock(return_value='ocr slides'),
    )
    runtime_model = Mock(
        model_entity=Mock(uuid='lno-paddleocr-vl-1-6', abilities=['pdf_parse'], prefered_ranking=0, extra_args={}),
        provider=provider,
    )
    ap = Mock(logger=Mock(), model_mgr=Mock(llm_models=[runtime_model]))
    monkeypatch.setattr(
        pdf_parse_service,
        'extract_text_from_bytes',
        Mock(return_value='local pptx'),
    )

    text = await pdf_parse_service.extract_document_text(ap, 'slides.pptx', b'PK\x03\x04')
    assert text == 'ocr slides'
    provider.invoke_pdf_parse.assert_awaited_once()
