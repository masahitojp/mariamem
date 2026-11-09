import json,time,statistics,hashlib
from pathlib import Path
import mariamem,pymysql
root=Path(__file__).resolve().parent
bins={n:str(root.parent/'temp'/f'{n}-host') for n in ('baseline','candidate')}
rows=[]
def connect(d):return pymysql.connect(**d.connection_info(),autocommit=True)
def seed(d):
 c=connect(d)
 with c.cursor() as q:
  q.execute('CREATE TABLE items(id INT PRIMARY KEY,payload BLOB) ENGINE=InnoDB')
  q.executemany('INSERT INTO items VALUES(%s,%s)',[(i,b'x'*1024) for i in range(1000)])
 c.close();d.wait_disconnected()
parents={}
try:
 for name,binary in bins.items():
  db=mariamem.Database(host_binary=binary);seed(db);parents[name]=db.snapshot()
 for origin in ('fresh','fork'):
  for write in (False,True):
   for repeat in range(6):
    for name in (('baseline','candidate') if repeat%2==0 else ('candidate','baseline')):
     d=mariamem.Database(host_binary=bins[name]) if origin=='fresh' else parents[name].fork()
     try:
      if origin=='fresh' and write:seed(d)
      if origin=='fork':
       c=connect(d)
       with c.cursor() as q:
        q.execute('SELECT COUNT(*),SUM(OCTET_LENGTH(payload)) FROM items');assert q.fetchone()==(1000,1024000)
        if write:q.execute("UPDATE items SET payload=REPEAT('y',1024)")
       c.close();d.wait_disconnected()
      start=time.perf_counter_ns();d.close();ms=(time.perf_counter_ns()-start)/1e6
      rows.append(dict(binary=name,origin=origin,write=write,repeat=repeat,close_ms=ms))
     finally:d.close()
finally:
 for s in parents.values():s.close()
(root/'matched-results.json').write_text(json.dumps(rows,indent=2)+'\n')
summary=[]
for origin in ('fresh','fork'):
 for write in (False,True):
  result=dict(origin=origin,write=write)
  for name in bins:
   values=[r['close_ms'] for r in rows if (r['binary'],r['origin'],r['write'])==(name,origin,write)]
   result[name]=statistics.median(values)
  summary.append(result)
(root/'matched-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
