import sqlite3, json
c=sqlite3.connect('data/langbot.db')
for uuid in ['a99c0949-e534-479c-8c6d-cae2d33ce4ae','lne-baidu-bge-large-zh']:
    r=c.execute('SELECT uuid,name,provider_uuid,extra_args FROM embedding_models WHERE uuid=?',(uuid,)).fetchone()
    print(uuid, r)
