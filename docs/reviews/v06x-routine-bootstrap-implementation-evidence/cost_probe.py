"""Small per-mode diagnostic cohort; no cross-version performance claim."""
import json, os, time
from pathlib import Path
import mariamem, pymysql
host=os.environ['MARIAMEM_ROUTINE_HOST']
rows=[]
for i in range(6):
 t=time.perf_counter(); db=mariamem.start(host_binary=host); fresh=(time.perf_counter()-t)*1000
 with pymysql.connect(**db.connection_info(),autocommit=True) as c:
  with c.cursor() as q:
   q.execute('CREATE FUNCTION test.cost_value() RETURNS INT DETERMINISTIC RETURN 9')
 db.wait_disconnected()
 t=time.perf_counter();baseline=db.snapshot();capture=(time.perf_counter()-t)*1000
 t=time.perf_counter();child=baseline.fork();fork=(time.perf_counter()-t)*1000
 with pymysql.connect(**child.connection_info(),autocommit=True) as c:
  with c.cursor() as q:
   q.execute('SELECT test.cost_value()');assert q.fetchall()==((9,),)
 t=time.perf_counter();child.close();close=(time.perf_counter()-t)*1000
 baseline.close();db.close()
 rows.append(dict(pair=i,host_pid=db._session._process.pid,fresh_ms=fresh,capture_ms=capture,fork_ms=fork,close_ms=close))
print(json.dumps({'classification':'diagnostic, six paired Fresh/Fork; timing observer on; not benchmark acceptance','rows':rows},indent=2))
