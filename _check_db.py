import sqlite3, json, os
from pathlib import Path

db = Path('data/langbot.db')
print('DB exists:', db.exists(), db.resolve())
if not db.exists():
    raise SystemExit(1)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
print('ALL TABLES:', tables)

keywords = ['embed', 'knowledge', 'kb', 'rag', 'model', 'provider', 'document', 'file', 'llm', 'ai']
print('RELEVANT TABLES:', [t for t in tables if any(k in t.lower() for k in keywords)])

def dump_table(name, limit=100):
    try:
        rows = cur.execute(f'SELECT * FROM {name} LIMIT {limit}').fetchall()
        cols = [r[1] for r in cur.execute(f'PRAGMA table_info({name})').fetchall()]
        print(f'\n--- {name} columns: {cols}')
        print(f'--- {name} count:', cur.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0])
        for r in rows[:20]:
            d = dict(r)
            # mask long secrets
            for k,v in list(d.items()):
                if v and isinstance(v, str) and any(x in k.lower() for x in ['key', 'secret', 'token', 'password']) and len(v)>8:
                    d[k] = v[:4]+'***'+v[-2:]+f'(len={len(v)})'
            print(d)
    except Exception as e:
        print(f'ERR {name}:', e)

for t in tables:
    if any(k in t.lower() for k in keywords):
        dump_table(t)

# status aggregation for kb files - try multiple table names
for tname in tables:
    if 'file' in tname.lower() or 'document' in tname.lower() or 'knowledge' in tname.lower():
        cols = [r[1] for r in cur.execute(f'PRAGMA table_info({tname})').fetchall()]
        for status_col in ['status', 'processing_status', 'file_status', 'state']:
            if status_col in cols:
                print(f'\n=== {tname} GROUP BY {status_col} ===')
                for row in cur.execute(f'SELECT {status_col}, COUNT(*) c FROM {tname} GROUP BY {status_col}'):
                    print(dict(row))
                for row in cur.execute(f"SELECT * FROM {tname} WHERE {status_col} IN ('failed','error','processing','pending','completed') LIMIT 0"):
                    pass
                try:
                    q = f"SELECT * FROM {tname} WHERE {status_col} IN ('failed','error') LIMIT 25"
                    failed = cur.execute(q).fetchall()
                    if failed:
                        print(f'FAILED in {tname}:')
                        for r in failed:
                            print(dict(r))
                except Exception as e:
                    print('failed query err', e)

conn.close()
