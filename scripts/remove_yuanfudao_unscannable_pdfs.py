from __future__ import annotations

import json
import sqlite3
import warnings
from pathlib import Path

from langbot.pkg.rag.knowledge.document_text import extract_text_from_bytes
from langbot.pkg.rag.knowledge.text_normalize import has_extractable_document_text

KB_UUID = 'yuanfudao-sales-knowledge-base'
PACK_DIR = Path('src/langbot/resources/templates/course-sales/yuanfudao-knowledge')
MANIFEST_PATH = PACK_DIR / 'manifest.json'
DB_PATH = Path('data/langbot.db')


def _is_unscannable_pdf(path: Path) -> bool:
    if path.suffix.lower() != '.pdf':
        return False
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        raw_text = extract_text_from_bytes(path.name, path.read_bytes())
    return not has_extractable_document_text(raw_text)


def _match_name(item: dict, name: str) -> bool:
    for key in ('name', 'source_name', 'storage_name'):
        if str(item.get(key) or '') == name:
            return True
    path_value = str(item.get('path') or '')
    return path_value.endswith(name)


def prune_manifest(removed_names: set[str]) -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    manifest_removed: list[str] = []

    for key in ('files', 'document_files'):
        items = manifest.get(key) or []
        kept = []
        for item in items:
            if not isinstance(item, dict):
                kept.append(item)
                continue
            name = str(item.get('name') or item.get('source_name') or item.get('storage_name') or '')
            if name in removed_names or any(_match_name(item, candidate) for candidate in removed_names):
                manifest_removed.append(name or str(item.get('path') or ''))
                continue
            kept.append(item)
        manifest[key] = kept

    manifest['total_files'] = len(manifest.get('files') or [])
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest_removed


def delete_pack_files(removed_names: set[str]) -> list[str]:
    deleted: list[str] = []
    documents_dir = PACK_DIR / 'documents'
    if not documents_dir.exists():
        return deleted
    for path in documents_dir.iterdir():
        if path.is_file() and path.name in removed_names:
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


def delete_db_records(removed_names: set[str]) -> tuple[list[str], list[str]]:
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
        base_name = Path(str(file_name or '')).name
        if base_name not in removed_names and str(file_name or '') not in removed_names:
            continue
        file_ids.append(str(file_uuid))
        conn.execute('DELETE FROM knowledge_base_files WHERE uuid = ?', (file_uuid,))
        removed.append(str(file_name))
    conn.commit()
    conn.close()
    return removed, file_ids


def discover_unscannable_pdfs() -> set[str]:
    documents_dir = PACK_DIR / 'documents'
    removed: set[str] = set()
    if not documents_dir.exists():
        return removed
    for path in sorted(documents_dir.glob('*.pdf')):
        if _is_unscannable_pdf(path):
            removed.add(path.name)
    return removed


def main() -> None:
    removed_names = discover_unscannable_pdfs()
    manifest_removed = prune_manifest(removed_names) if removed_names else []
    pack_deleted = delete_pack_files(removed_names)
    db_removed, file_ids = delete_db_records(removed_names)
    chroma_deleted = delete_chroma_vectors(file_ids)
    print(
        json.dumps(
            {
                'detected_unscannable': sorted(removed_names),
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
