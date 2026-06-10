from __future__ import annotations

import json
import sqlite3
from pathlib import Path

KB_UUID = 'yuanfudao-sales-knowledge-base'
DB_PATH = Path('data/langbot.db')
CHROMA_PATH = Path('data/chroma')


def _delete_chroma_vectors() -> int:
    if not CHROMA_PATH.exists():
        return 0
    try:
        import chromadb
    except ImportError:
        return 0

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        collection = client.get_collection(KB_UUID)
    except Exception:
        return 0

    data = collection.get(include=[])
    ids = data.get('ids') or []
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def _delete_kb_file_records() -> int:
    if not DB_PATH.exists():
        return 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('DELETE FROM knowledge_base_files WHERE kb_id = ?', (KB_UUID,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def main() -> None:
    deleted_vectors = _delete_chroma_vectors()
    deleted_files = _delete_kb_file_records()
    print(
        json.dumps(
            {
                'knowledge_base_uuid': KB_UUID,
                'deleted_vectors': deleted_vectors,
                'deleted_file_records': deleted_files,
                'next_step': 'Restart LangBot backend to re-import and re-index Yuanfudao documents.',
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
