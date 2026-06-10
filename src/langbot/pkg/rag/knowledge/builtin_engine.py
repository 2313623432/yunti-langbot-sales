from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import asyncio

from langbot.pkg.core import app
from langbot.pkg.rag.knowledge.pdf_parse_service import extract_document_text
from langbot.pkg.rag.knowledge.text_normalize import (
    clean_ingestion_text,
    has_extractable_document_text,
    is_meaningful_chunk,
    is_meaningful_document,
)

BUILTIN_KNOWLEDGE_ENGINE_ID = 'langbot/BuiltinRAG'
DEFAULT_CHUNK_SIZE = 250
DEFAULT_CHUNK_OVERLAP = 50
MAX_EMBEDDING_CHUNK_CHARS = 250
EMBED_BATCH_SIZE = 10
EMBED_RETRY_ATTEMPTS = 4
EMBED_RETRY_BASE_DELAY_SECONDS = 2.0

_CREATION_SCHEMA = [
    {
        'name': 'embedding_model_uuid',
        'type': 'embedding-model-selector',
        'label': {
            'en_US': 'Embedding Model',
            'zh_Hans': 'Embedding 模型',
            'zh_Hant': 'Embedding 模型',
        },
        'description': {
            'en_US': 'Embedding model used to index and retrieve documents.',
            'zh_Hans': '用于文档索引与检索的 Embedding 模型。',
            'zh_Hant': '用於文件索引與檢索的 Embedding 模型。',
        },
        'required': True,
    },
    {
        'name': 'chunk_size',
        'type': 'number',
        'label': {
            'en_US': 'Chunk Size',
            'zh_Hans': '分块大小',
            'zh_Hant': '分塊大小',
        },
        'default': DEFAULT_CHUNK_SIZE,
        'required': False,
    },
    {
        'name': 'chunk_overlap',
        'type': 'number',
        'label': {
            'en_US': 'Chunk Overlap',
            'zh_Hans': '分块重叠',
            'zh_Hant': '分塊重疊',
        },
        'default': DEFAULT_CHUNK_OVERLAP,
        'required': False,
    },
]

_RETRIEVAL_SCHEMA = [
    {
        'name': 'top_k',
        'type': 'number',
        'label': {
            'en_US': 'Top K',
            'zh_Hans': '返回条数',
            'zh_Hant': '返回條數',
        },
        'default': 5,
        'required': False,
    },
]


def is_builtin_knowledge_engine(plugin_id: str | None) -> bool:
    return plugin_id == BUILTIN_KNOWLEDGE_ENGINE_ID


def get_builtin_engine_info() -> dict[str, Any]:
    return {
        'plugin_id': BUILTIN_KNOWLEDGE_ENGINE_ID,
        'name': {
            'en_US': 'LangBot Builtin RAG',
            'zh_Hans': '内置知识库',
            'zh_Hant': '內建知識庫',
        },
        'capabilities': ['doc_ingestion', 'search'],
        'creation_schema': _CREATION_SCHEMA,
        'retrieval_schema': _RETRIEVAL_SCHEMA,
    }


def get_builtin_creation_schema() -> list[dict[str, Any]]:
    return _CREATION_SCHEMA


def get_builtin_retrieval_schema() -> list[dict[str, Any]]:
    return _RETRIEVAL_SCHEMA


def split_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    if chunk_size <= 0:
        chunk_size = DEFAULT_CHUNK_SIZE
    if overlap < 0:
        overlap = 0
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end])
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def normalize_chunks_for_embedding(chunks: list[str], max_chars: int = MAX_EMBEDDING_CHUNK_CHARS) -> list[str]:
    if max_chars <= 0:
        max_chars = MAX_EMBEDDING_CHUNK_CHARS
    normalized: list[str] = []
    for chunk in chunks:
        stripped = chunk.strip()
        if not stripped:
            continue
        if len(stripped) <= max_chars:
            normalized.append(stripped)
            continue
        normalized.extend(split_text(stripped, chunk_size=max_chars, overlap=0))
    return normalized


class BuiltinKnowledgeEngine:
    """Built-in knowledge engine backed by LangBot vector store and embedding models."""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def on_kb_create(self, kb_id: str, collection_id: str, config: dict[str, Any]) -> dict[str, Any]:
        _ = kb_id, collection_id, config
        return {'success': True}

    async def on_kb_delete(self, kb_id: str, collection_id: str) -> dict[str, Any]:
        if self.ap.vector_db_mgr is None:
            return {'success': True}
        try:
            await self.ap.vector_db_mgr.delete_collection(collection_id)
        except Exception as exc:
            self.ap.logger.warning('Failed to delete builtin KB collection %s: %s', collection_id, exc)
        return {'success': True}

    async def ingest(
        self,
        *,
        kb_id: str,
        collection_id: str,
        creation_settings: dict[str, Any],
        file_metadata: dict[str, Any],
        storage_path: str,
        parsed_content: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        document_id = str(file_metadata.get('document_id') or file_metadata.get('uuid') or uuid.uuid4())
        filename = str(file_metadata.get('filename') or storage_path)
        raw_text = await self.extract_text_async(parsed_content, storage_path)
        if not has_extractable_document_text(raw_text):
            return {
                'status': 'failed',
                'error_message': f'Insufficient extractable text in {filename}',
            }

        text = clean_ingestion_text(raw_text)
        if not is_meaningful_document(text):
            return {
                'status': 'failed',
                'error_message': f'Insufficient meaningful text extracted from {filename}',
            }

        chunk_size = int(creation_settings.get('chunk_size') or DEFAULT_CHUNK_SIZE)
        chunk_overlap = int(creation_settings.get('chunk_overlap') or DEFAULT_CHUNK_OVERLAP)
        chunks = [
            chunk
            for chunk in normalize_chunks_for_embedding(
                split_text(text, chunk_size=chunk_size, overlap=chunk_overlap),
                max_chars=min(chunk_size, MAX_EMBEDDING_CHUNK_CHARS),
            )
            if is_meaningful_chunk(chunk)
        ]
        if not chunks:
            return {
                'status': 'failed',
                'error_message': f'Failed to chunk document {filename}',
            }

        embedding_model = await self._get_embedding_model(creation_settings)
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []
        documents: list[str] = []

        for index, chunk in enumerate(chunks):
            chunk_id = f'{document_id}:{index}'
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(
                {
                    'file_id': document_id,
                    'knowledge_base_id': kb_id,
                    'filename': filename,
                    'document_name': filename,
                    'chunk_index': index,
                    'text': chunk,
                }
            )

        vectors: list[list[float]] = []
        for start in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[start : start + EMBED_BATCH_SIZE]
            batch_vectors = await self._embed_with_retry(embedding_model, batch)
            vectors.extend(batch_vectors)

        await self.ap.rag_runtime_service.vector_upsert(
            collection_id,
            vectors,
            ids,
            metadata=metadatas,
            documents=documents,
        )
        return {'status': 'success', 'chunk_count': len(chunks)}

    async def retrieve(
        self,
        *,
        query: str,
        kb_id: str,
        collection_id: str,
        creation_settings: dict[str, Any],
        retrieval_settings: dict[str, Any],
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        top_k = int(retrieval_settings.get('top_k') or 5)
        embedding_model = await self._get_embedding_model(creation_settings)
        query_vectors = await embedding_model.provider.invoke_embedding(embedding_model, [query])
        if not query_vectors:
            return {'results': []}

        raw_results = await self.ap.rag_runtime_service.vector_search(
            collection_id,
            query_vectors[0],
            top_k,
            filters=filters,
        )

        results = []
        for item in raw_results:
            metadata = item.get('metadata') or {}
            content_text = str(metadata.get('text') or item.get('document') or '')
            results.append(
                {
                    'id': item.get('id', ''),
                    'content': [{'type': 'text', 'text': content_text}],
                    'metadata': metadata,
                    'distance': item.get('distance', 0.0),
                }
            )
        return {'results': results}

    async def delete_document(self, document_id: str, collection_id: str) -> bool:
        await self.ap.rag_runtime_service.vector_delete(collection_id, file_ids=[document_id])
        return True

    async def _get_embedding_model(self, creation_settings: dict[str, Any]):
        embedding_model_uuid = str(creation_settings.get('embedding_model_uuid') or '').strip()
        if not embedding_model_uuid:
            raise ValueError('embedding_model_uuid is required for builtin knowledge engine')
        embedding_model = await self.ap.model_mgr.get_embedding_model_by_uuid(embedding_model_uuid)
        if embedding_model is None:
            raise ValueError(f'Embedding model {embedding_model_uuid} not found')
        return embedding_model

    async def _embed_with_retry(self, embedding_model, batch: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for attempt in range(EMBED_RETRY_ATTEMPTS):
            try:
                return await embedding_model.provider.invoke_embedding(embedding_model, batch)
            except Exception as exc:
                last_error = exc
                if attempt >= EMBED_RETRY_ATTEMPTS - 1:
                    break
                delay = EMBED_RETRY_BASE_DELAY_SECONDS * (2**attempt)
                if getattr(self.ap, 'logger', None) is not None:
                    self.ap.logger.warning(
                        'Embedding batch failed (attempt %s/%s), retrying in %.1fs: %s',
                        attempt + 1,
                        EMBED_RETRY_ATTEMPTS,
                        delay,
                        exc,
                    )
                await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error

    async def extract_text_async(self, parsed_content: dict[str, Any] | None, storage_path: str) -> str:
        if parsed_content:
            for key in ('text', 'content', 'markdown'):
                value = parsed_content.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            blocks = parsed_content.get('blocks')
            if isinstance(blocks, list):
                parts = []
                for block in blocks:
                    if isinstance(block, dict):
                        text = block.get('text') or block.get('content')
                        if isinstance(text, str) and text.strip():
                            parts.append(text)
                if parts:
                    return '\n\n'.join(parts)

        content_bytes = await self.ap.rag_runtime_service.get_file_stream(storage_path)
        filename = Path(storage_path).name
        return await extract_document_text(self.ap, filename, content_bytes)
