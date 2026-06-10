from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from langbot.pkg.rag.knowledge.document_text import extract_text_from_bytes
from langbot.pkg.rag.knowledge.text_normalize import (
    clean_ingestion_text,
    has_extractable_document_text,
    is_meaningful_document,
)

KB_UUID = 'yuanfudao-sales-knowledge-base'
PACK_DIR = Path('src/langbot/resources/templates/course-sales/yuanfudao-knowledge')
MANIFEST_PATH = PACK_DIR / 'manifest.json'
DOCUMENTS_DIR = PACK_DIR / 'documents'
DB_PATH = Path('data/langbot.db')


def _is_bad_pdf_name(name: str) -> bool:
    return Path(name).suffix.lower() == '.pdf'


def audit_bad_pdf_names() -> list[str]:
    bad_names: list[str] = []
    if not DOCUMENTS_DIR.exists():
        return bad_names
    for path in sorted(DOCUMENTS_DIR.glob('*.pdf')):
        extracted = extract_text_from_bytes(path.name, path.read_bytes())
        if not has_extractable_document_text(extracted) or not is_meaningful_document(clean_ingestion_text(extracted)):
            bad_names.append(path.name)
    return bad_names


def prune_manifest(bad_names: set[str]) -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    removed_names: list[str] = []

    for key in ('files', 'document_files'):
        items = manifest.get(key) or []
        kept = []
        for item in items:
            if not isinstance(item, dict):
                kept.append(item)
                continue
            name = str(item.get('name') or item.get('source_name') or item.get('storage_name') or '')
            ext = str(item.get('extension') or Path(name).suffix).lower()
            if ext == '.pdf' and (name in bad_names or Path(name).name in bad_names):
                removed_names.append(name or str(item.get('path') or ''))
                continue
            kept.append(item)
        manifest[key] = kept

    manifest['total_files'] = len(manifest.get('files') or [])
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return removed_names


def delete_pack_files(bad_names: set[str]) -> list[str]:
    deleted: list[str] = []
    if not DOCUMENTS_DIR.exists():
        return deleted
    for path in DOCUMENTS_DIR.iterdir():
        if path.is_file() and path.name in bad_names:
            deleted.append(path.name)
            path.unlink()
    return deleted


def delete_chroma_vectors(file_ids: list[str]) -> int:
    chroma_path = Path('data/chroma')
    if not chroma_path.exists() or not file_ids:
        return 0
    try:
        import chromadb
    except ImportError:
        return 0
    client = chromadb.PersistentClient(path=str(chroma_path))
    try:
        col = client.get_collection(KB_UUID)
    except Exception:
        return 0
    deleted = 0
    for file_id in file_ids:
        try:
            col.delete(where={'file_id': file_id})
            deleted += 1
        except Exception:
            continue
    return deleted


def delete_db_records(bad_names: set[str]) -> tuple[list[str], list[str]]:
    if not DB_PATH.exists():
        return [], []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        'SELECT uuid, file_name FROM knowledge_base_files WHERE kb_id = ?',
        (KB_UUID,),
    ).fetchall()
    removed: list[str] = []
    file_ids: list[str] = []
    for file_uuid, file_name in rows:
        raw_name = str(file_name or '')
        if raw_name not in bad_names and Path(raw_name).name not in bad_names:
            continue
        file_ids.append(str(file_uuid))
        conn.execute('DELETE FROM knowledge_base_files WHERE uuid = ?', (file_uuid,))
        removed.append(raw_name)
    conn.commit()
    conn.close()
    return removed, file_ids


def main() -> None:
    bad_names = set(audit_bad_pdf_names())
    manifest_removed = prune_manifest(bad_names)
    pack_deleted = delete_pack_files(bad_names)
    db_removed, file_ids = delete_db_records(bad_names)
    chroma_deleted = delete_chroma_vectors(file_ids)
    print(
        json.dumps(
            {
                'bad_pdf_names': sorted(bad_names),
                'manifest_removed': manifest_removed,
                'pack_deleted': pack_deleted,
                'db_removed': db_removed,
                'chroma_file_ids_deleted': chroma_deleted,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
