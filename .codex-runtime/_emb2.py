import sqlite3, json
c=sqlite3.connect('data/langbot.db')
c.row_factory=sqlite3.Row
for t in ['llm_models','embedding_models']:
    r=c.execute(f'SELECT * FROM {t} WHERE uuid=?',('a99c0949-e534-479c-8c6d-cae2d33ce4ae',)).fetchone()
    print(t, dict(r) if r else None)
print('--- pdf related providers ---')
for r in c.execute("SELECT uuid,name,requester,base_url,api_keys FROM model_providers WHERE name LIKE '%Paddle%' OR name LIKE '%MinerU%' OR uuid LIKE '%pdf%'"):
    d=dict(r)
    keys=json.loads(d.pop('api_keys') or '[]')
    d['api_keys_count']=len(keys)
    d['has_key']=any(len(str(k))>4 for k in keys)
    print(d)
print('--- pdf models table? ---')
tables=[x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print([t for t in tables if 'pdf' in t.lower()])
