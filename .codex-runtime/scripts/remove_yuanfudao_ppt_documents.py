from __future__ import annotations

import json
import sqlite3
from pathlib import Path

KB_UUID = 'yuanfudao-sales-knowledge-base'
PACK_DIR = Path('src/langbot/resources/templates/course-sales/yuanfudao-knowledge')
MANIFEST_PATH = PACK_DIR / 'manifest.json'
DB_PATH = Path('data/langbot.db')
PPT_EXTENSIONS = {'.ppt', '.pptx'}


def _is_ppt_name(name: str) -> bool:
    return Path(name).suffix.lower() in PPT_EXTENSIONS


def prune_manifest() -> list[str]:
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
            if ext in PPT_EXTENSIONS or _is_ppt_name(name):
                removed_names.append(name or str(item.get('path') or ''))
                continue
            kept.append(item)
        manifest[key] = kept

    manifest['total_files'] = len(manifest.get('files') or [])
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return removed_names


def delete_pack_files() -> list[str]:
    deleted: list[str] = []
    documents_dir = PACK_DIR / 'documents'
    if not documents_dir.exists():
        return deleted
    for path in documents_dir.iterdir():
        if path.is_file() and path.suffix.lower() in PPT_EXTENSIONS:
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


def delete_db_records() -> tuple[list[str], list[str]]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT uuid, file_name FROM knowledge_base_files WHERE kb_id = ?",
        (KB_UUID,),
    ).fetchall()
    removed: list[str] = []
    file_ids: list[str] = []
    for file_uuid, file_name in rows:
        if not _is_ppt_name(str(file_name or '')):
            continue
        file_ids.append(str(file_uuid))
        conn.execute('DELETE FROM knowledge_base_files WHERE uuid = ?', (file_uuid,))
        removed.append(str(file_name))
    conn.commit()
    conn.close()
    return removed, file_ids


def main() -> None:
    manifest_removed = prune_manifest()
    pack_deleted = delete_pack_files()
    db_removed, file_ids = delete_db_records()
    chroma_deleted = delete_chroma_vectors(file_ids)
    print(
        json.dumps(
            {
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
