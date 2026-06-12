import sqlite3, json
c=sqlite3.connect('data/langbot.db')
c.row_factory=sqlite3.Row
print('status counts', [dict(r) for r in c.execute('SELECT status, COUNT(*) c FROM knowledge_base_files GROUP BY status')])
print('total', c.execute('SELECT COUNT(*) FROM knowledge_base_files').fetchone()[0])
for r in c.execute("SELECT file_name, extension, status FROM knowledge_base_files WHERE status!='completed' ORDER BY status, file_name"):
    print(dict(r))
# workflow seed
r=c.execute('SELECT * FROM workflow_seed_state').fetchone()
if r: print('seed', dict(r))
