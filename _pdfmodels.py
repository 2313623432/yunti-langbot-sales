import sqlite3, json
c=sqlite3.connect('data/langbot.db')
c.row_factory=sqlite3.Row
for r in c.execute("SELECT uuid,name,provider_uuid,abilities,extra_args,prefered_ranking FROM llm_models WHERE abilities LIKE '%pdf%' OR name LIKE '%Paddle%' OR name LIKE '%MinerU%' OR uuid LIKE 'ln%'"):
    d=dict(r)
    d['abilities']=json.loads(d['abilities'] or '[]')
    d['extra_args']=json.loads(d['extra_args'] or '{}')
    pu=c.execute('SELECT uuid,name,requester,base_url,api_keys FROM model_providers WHERE uuid=?',(d['provider_uuid'],)).fetchone()
    pd=dict(pu) if pu else {}
    keys=json.loads(pd.get('api_keys') or '[]')
    pd['api_keys_count']=len(keys)
    pd['has_key']=any(len(str(k))>4 for k in keys)
    print('MODEL', json.dumps(d, ensure_ascii=False))
    print('PROV', json.dumps({k:pd[k] for k in ['uuid','name','requester','base_url','api_keys_count','has_key']}, ensure_ascii=False))
