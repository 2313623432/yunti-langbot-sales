from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path('data/langbot.db')
KB_UUID = 'yuanfudao-sales-knowledge-base'
BAIDU_EMBEDDING_UUID = 'lne-baidu-bge-large-zh'


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'UPDATE knowledge_bases SET creation_settings = ? WHERE uuid = ?',
        (
            json.dumps(
                {
                    'embedding_model_uuid': BAIDU_EMBEDDING_UUID,
                    'chunk_size': 250,
                    'chunk_overlap': 50,
                }
            ),
            KB_UUID,
        ),
    )
    cursor = conn.execute(
        "DELETE FROM knowledge_base_files WHERE kb_id = ? AND status = 'failed'",
        (KB_UUID,),
    )
    conn.commit()
    print(
        json.dumps(
            {
                'embedding_model_uuid': BAIDU_EMBEDDING_UUID,
                'deleted_failed_files': cursor.rowcount,
            },
            ensure_ascii=False,
        )
    )
    conn.close()


if __name__ == '__main__':
    main()
