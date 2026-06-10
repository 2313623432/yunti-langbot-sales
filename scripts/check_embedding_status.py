from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path('data/langbot.db')


def main() -> None:
    conn = sqlite3.connect(DB)
    print('=== Providers ===')
    for row in conn.execute(
        "SELECT uuid, name, base_url, api_keys FROM model_providers "
        "WHERE uuid LIKE 'lne-%' OR name LIKE '%Embedding%' OR name LIKE '%星河%'"
    ):
        keys = json.loads(row[3] or '[]')
        print(f'{row[0]} | {row[1]} | {row[2]} | key: {"yes" if keys else "no"}')
    print('=== Embedding Models ===')
    for row in conn.execute(
        "SELECT uuid, name, provider_uuid, extra_args FROM embedding_models "
        "WHERE uuid LIKE 'lne-%'"
    ):
        print(row)
    print('=== KB ===')
    row = conn.execute(
        "SELECT creation_settings FROM knowledge_bases WHERE uuid='yuanfudao-sales-knowledge-base'"
    ).fetchone()
    print(row[0] if row else 'not found')
    print('=== File status ===')
    for row in conn.execute(
        "SELECT status, COUNT(*) FROM knowledge_base_files "
        "WHERE kb_id='yuanfudao-sales-knowledge-base' GROUP BY status"
    ):
        print(row)
    conn.close()


if __name__ == '__main__':
    main()
