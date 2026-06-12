import sqlite3, json
conn = sqlite3.connect('data/langbot.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('=== Baidu providers ===')
for r in cur.execute("SELECT uuid, name, requester, base_url, api_keys FROM model_providers WHERE uuid LIKE '%baidu%' OR name LIKE '%百度%' OR name LIKE '%Baidu%'"):
    d = dict(r)
    keys = d.pop('api_keys')
    try:
        kl = json.loads(keys) if keys else []
    except:
        kl = keys
    if isinstance(kl, list):
        d['api_keys_count'] = len(kl)
        d['api_keys_set'] = [bool(x and len(str(x))>4) for x in kl]
        d['api_key_lens'] = [len(str(x)) for x in kl]
    print(json.dumps(d, ensure_ascii=False))

print('\n=== KB creation_settings ===')
for r in cur.execute('SELECT uuid, name, creation_settings, collection_id FROM knowledge_bases'):
    d = dict(r)
    if d.get('creation_settings'):
        d['creation_settings'] = json.loads(d['creation_settings'])
    print(json.dumps(d, ensure_ascii=False, indent=2))

print('\n=== processing/pending ===')
for r in cur.execute("SELECT file_name, extension, status FROM knowledge_base_files WHERE status IN ('processing','pending')"):
    print(dict(r))

print('\n=== embedding monitoring summary ===')
for r in cur.execute("SELECT model_name, status, COUNT(*) c FROM monitoring_embedding_calls GROUP BY model_name, status ORDER BY c DESC"):
    print(dict(r))

print('\n=== bge recent ===')
for r in cur.execute("SELECT timestamp, model_name, status, error_message, input_count FROM monitoring_embedding_calls WHERE model_name LIKE '%bge%' ORDER BY timestamp DESC LIMIT 15"):
    print(dict(r))

print('\n=== monitoring_errors recent ===')
try:
    for r in cur.execute("SELECT * FROM monitoring_errors ORDER BY rowid DESC LIMIT 20"):
        print(dict(r))
except Exception as e:
    print('monitoring_errors', e)

print('\n=== plugin_settings OCR related ===')
for r in cur.execute("SELECT * FROM plugin_settings"):
    d = dict(r)
    s = json.dumps(d, ensure_ascii=False)
    if any(k in s.lower() for k in ['ocr', 'paddle', 'baidu', 'embed', 'knowledge']):
        print(s[:500])

print('\n=== metadata ===')
for r in cur.execute('SELECT * FROM metadata'):
    print(dict(r))

conn.close()
