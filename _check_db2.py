import sqlite3, json
from pathlib import Path

conn = sqlite3.connect('data/langbot.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('=== model_providers (baidu/aistudio/paddle/lne) ===')
for r in cur.execute("SELECT uuid, name, provider_type, extra_args FROM model_providers"):
    d = dict(r)
    s = json.dumps(d, ensure_ascii=False)
    if any(k in s.lower() for k in ['baidu', 'aistudio', 'paddle', 'lne-baidu', 'embedding', 'ocr']):
        ea = d.get('extra_args') or '{}'
        try:
            j = json.loads(ea) if isinstance(ea, str) else ea
        except:
            j = ea
        masked = {}
        if isinstance(j, dict):
            for k,v in j.items():
                if isinstance(v, str) and any(x in k.lower() for x in ['key','token','secret']) and len(v)>6:
                    masked[k] = f'{v[:6]}... (len={len(v)})'
                else:
                    masked[k] = v
        else:
            masked = j
        print({'uuid': d['uuid'], 'name': d['name'], 'provider_type': d['provider_type'], 'extra_args': masked})

print('\n=== knowledge_bases ===')
for r in cur.execute('SELECT * FROM knowledge_bases'):
    d = dict(r)
    cs = d.get('creation_settings')
    if cs:
        try:
            d['creation_settings'] = json.loads(cs)
        except:
            pass
    print(json.dumps(d, ensure_ascii=False, indent=2))

print('\n=== file status counts ===')
for row in cur.execute('SELECT status, COUNT(*) c FROM knowledge_base_files GROUP BY status'):
    print(dict(row))

print('\n=== processing/pending files ===')
for r in cur.execute("SELECT file_name, extension, status FROM knowledge_base_files WHERE status IN ('processing','pending')"):
    print(dict(r))

print('\n=== failed files ===')
for r in cur.execute("SELECT file_name, extension, status FROM knowledge_base_files WHERE status='failed' ORDER BY file_name"):
    print(dict(r))

print('\n=== recent bge embedding calls ===')
for r in cur.execute("SELECT timestamp, model_name, status, error_message FROM monitoring_embedding_calls WHERE model_name LIKE '%bge%' OR model_name LIKE '%large-zh%' ORDER BY timestamp DESC LIMIT 10"):
    print(dict(r))

print('\n=== recent embedding errors (429/quota) ===')
for r in cur.execute("SELECT timestamp, model_name, status, substr(error_message,1,200) err FROM monitoring_embedding_calls WHERE status='error' AND (error_message LIKE '%429%' OR error_message LIKE '%quota%') ORDER BY timestamp DESC LIMIT 10"):
    print(dict(r))

print('\n=== recent embedding success bge ===')
for r in cur.execute("SELECT timestamp, model_name, status, input_count FROM monitoring_embedding_calls WHERE status='success' AND (model_name LIKE '%bge%' OR model_name LIKE '%large%') ORDER BY timestamp DESC LIMIT 5"):
    print(dict(r))

conn.close()
