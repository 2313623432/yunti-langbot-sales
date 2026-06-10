from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/langbot.db")
KB_UUID = "yuanfudao-sales-knowledge-base"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "DELETE FROM knowledge_base_files "
        "WHERE kb_id = ? AND status IN ('failed', 'processing', 'pending') "
        "AND file_name LIKE '%.pdf'",
        (KB_UUID,),
    )
    conn.commit()
    print(json.dumps({"deleted_pdf_files": cursor.rowcount}, ensure_ascii=False))
    conn.close()


if __name__ == "__main__":
    main()
