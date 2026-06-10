from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock

from langbot.pkg.rag.knowledge import builtin_engine


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
    mock_app.rag_runtime_service.get_file_stream = AsyncMock(return_value=b'hello world')
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
