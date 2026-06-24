from __future__ import annotations

import pytest
from importlib import import_module
from unittest.mock import AsyncMock, Mock

import_module('langbot.pkg.rag.knowledge.kbmgr')
builtin_engine = import_module('langbot.pkg.rag.knowledge.builtin_engine')


def test_split_text_returns_single_chunk_for_short_text():
    text = 'hello world'
    assert builtin_engine.split_text(text, chunk_size=100) == [text]


def test_split_text_splits_long_text_with_overlap():
    text = 'a' * 1000
    chunks = builtin_engine.split_text(text, chunk_size=400, overlap=50)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 400 for chunk in chunks)


def test_normalize_chunks_for_embedding_splits_oversized_chunk():
    chunks = ['short', '中' * 600]
    normalized = builtin_engine.normalize_chunks_for_embedding(chunks, max_chars=250)
    assert normalized[0] == 'short'
    assert len(normalized) >= 3
    assert all(len(chunk) <= 250 for chunk in normalized)


def test_get_builtin_engine_info_exposes_capabilities():
    info = builtin_engine.get_builtin_engine_info()
    assert info['plugin_id'] == builtin_engine.BUILTIN_KNOWLEDGE_ENGINE_ID
    assert 'doc_ingestion' in info['capabilities']
    assert 'search' in info['capabilities']


@pytest.mark.asyncio
async def test_builtin_engine_ingest_rejects_empty_pdf_text():
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.model_mgr = AsyncMock()
    mock_app.rag_runtime_service = AsyncMock()
    mock_app.rag_runtime_service.get_file_stream = AsyncMock(return_value=b'%PDF-1.4')
    mock_app.rag_runtime_service.vector_upsert = AsyncMock()

    engine = builtin_engine.BuiltinKnowledgeEngine(mock_app)
    result = await engine.ingest(
        kb_id='kb-1',
        collection_id='kb-1',
        creation_settings={'embedding_model_uuid': 'embed-1'},
        file_metadata={'document_id': 'doc-1', 'filename': 'scan.pdf'},
        storage_path='scan.pdf',
        parsed_content=None,
    )

    assert result['status'] == 'failed'
    assert 'Insufficient extractable text' in result['error_message']
    mock_app.rag_runtime_service.vector_upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_builtin_engine_ingest_rejects_garbage_pdf_text():
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.model_mgr = AsyncMock()
    mock_app.rag_runtime_service = AsyncMock()
    garbage = (
        'e YUANFUDAO e YUANFUDAO e YUANFUDAO e YUANFUDAO e YUANFUDAO e YUANFUDAO\n'
        '1-6\nD猿辅导\n小学生必背古诗词\n'
        ',; YUANFUDAO ,; YUANFUDAO ,; YUANFUDAO ,; YUANFUDAO ,; YUANFUDAO ,; YUANFUDAO\n'
        'YUANFUDAO YUANFUDAO YUANFUDAO YUANFUDAO YUANFUDAO YUANFUDAO YUANFUDAO YUANFUDAO'
    )
    mock_app.rag_runtime_service.get_file_stream = AsyncMock(return_value=garbage.encode('utf-8'))
    mock_app.rag_runtime_service.vector_upsert = AsyncMock()

    engine = builtin_engine.BuiltinKnowledgeEngine(mock_app)
    result = await engine.ingest(
        kb_id='kb-1',
        collection_id='kb-1',
        creation_settings={'embedding_model_uuid': 'embed-1'},
        file_metadata={'document_id': 'doc-1', 'filename': 'scan.pdf'},
        storage_path='scan.pdf',
        parsed_content={'text': garbage},
    )

    assert result['status'] == 'failed'
    assert 'Insufficient' in result['error_message']
    mock_app.rag_runtime_service.vector_upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_builtin_engine_ingest_rejects_empty_document():
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.model_mgr = AsyncMock()
    mock_app.rag_runtime_service = AsyncMock()
    mock_app.rag_runtime_service.get_file_stream = AsyncMock(return_value=b'')
    mock_app.rag_runtime_service.vector_upsert = AsyncMock()

    engine = builtin_engine.BuiltinKnowledgeEngine(mock_app)
    result = await engine.ingest(
        kb_id='kb-1',
        collection_id='kb-1',
        creation_settings={'embedding_model_uuid': 'embed-1'},
        file_metadata={'document_id': 'doc-1', 'filename': 'scan.pdf'},
        storage_path='scan.pdf',
        parsed_content=None,
    )

    assert result['status'] == 'failed'
    mock_app.rag_runtime_service.vector_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_builtin_engine_ingest_upserts_vectors():
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_embedding_model = Mock()
    mock_embedding_model.provider.invoke_embedding = AsyncMock(
        return_value=[[0.1, 0.2], [0.3, 0.4]]
    )
    mock_app.model_mgr = AsyncMock()
    mock_app.model_mgr.get_embedding_model_by_uuid = AsyncMock(return_value=mock_embedding_model)
    mock_app.rag_runtime_service = AsyncMock()
    sample_text = (
        '自然拼读是我们英语的底层逻辑，学会自然拼读可以让孩子快速增加单词储备量。'
        '课程覆盖小学核心词汇与常见语法点，适合作为销售话术中的专业背书。'
        '家长常问的问题包括课程时长、师资背景、续费政策与退费规则，需要结合最新活动页说明。'
    )
    mock_app.rag_runtime_service.get_file_stream = AsyncMock(
        return_value=(sample_text * 6).encode('utf-8')
    )
    mock_app.rag_runtime_service.vector_upsert = AsyncMock()

    engine = builtin_engine.BuiltinKnowledgeEngine(mock_app)
    result = await engine.ingest(
        kb_id='kb-1',
        collection_id='kb-1',
        creation_settings={'embedding_model_uuid': 'embed-1'},
        file_metadata={'document_id': 'doc-1', 'filename': 'note.md'},
        storage_path='note.md',
        parsed_content=None,
    )

    assert result['status'] == 'success'
    mock_app.rag_runtime_service.vector_upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_builtin_engine_retrieve_returns_entries():
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_embedding_model = Mock()
    mock_embedding_model.provider.invoke_embedding = AsyncMock(
        return_value=[[0.5, 0.6]]
    )
    mock_app.model_mgr = AsyncMock()
    mock_app.model_mgr.get_embedding_model_by_uuid = AsyncMock(return_value=mock_embedding_model)
    mock_app.rag_runtime_service = AsyncMock()
    mock_app.rag_runtime_service.vector_search = AsyncMock(
        return_value=[
            {
                'id': 'doc-1:0',
                'distance': 0.12,
                'metadata': {'text': 'matched chunk', 'filename': 'note.md'},
            }
        ]
    )

    engine = builtin_engine.BuiltinKnowledgeEngine(mock_app)
    result = await engine.retrieve(
        query='hello',
        kb_id='kb-1',
        collection_id='kb-1',
        creation_settings={'embedding_model_uuid': 'embed-1'},
        retrieval_settings={'top_k': 3},
        filters=None,
    )

    assert len(result['results']) == 1
    assert result['results'][0]['content'][0]['text'] == 'matched chunk'
