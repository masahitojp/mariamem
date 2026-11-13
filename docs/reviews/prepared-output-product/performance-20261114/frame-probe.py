from pathlib import Path
import sys,hashlib,json,time
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);w=parser.parse_args().workspace.resolve();sys.path.insert(0,str(w/'candidate/python'))
import mariamem,mysql.connector
result={'scope':'real guest single binary row near length-prefix/32MiB JSON envelope; each case owns DB; errors and following-query captured without recovery assumption','sources':{'baseline':'eb175ae23292c1c40cfbeb4b9b73132873c4cc6f','candidate':'d0aca17352708c5cb85812e0f4c11b228d3006e7'},'runs':[]}
def error(e):return {'type':type(e).__name__,'errno':getattr(e,'errno',None),'sqlstate':getattr(e,'sqlstate',None),'message':str(e)}
for variant in ['baseline','candidate']:
 for size in [65535,65536,65537,(16<<20)-1024,(16<<20)-1]:
  case={'variant':variant,'payload_bytes':size};db=None;c=None;start=time.monotonic()
  try:
   db=mariamem.start(host_binary=str(w/'artifacts'/(variant+'-host')));c=mysql.connector.connect(**db.connection_info(),use_pure=True,autocommit=True,read_timeout=60)
   try:
    with c.cursor(prepared=True) as q:
     q.execute("SELECT REPEAT(CAST('x' AS BINARY), ?) AS payload",(size,));rows=q.fetchall();assert rows==[(b'x'*size,)],(variant,size,'value mismatch')
     case.update(result='ROW',sha256=hashlib.sha256(rows[0][0]).hexdigest(),columns=[(d[0],d[1]) for d in q.description])
   except mysql.connector.Error as e:case.update(result='ERR',error=error(e))
   try:
    with c.cursor() as q:q.execute('SELECT 1');assert q.fetchone()==(1,);case['following_query']='PASS'
   except mysql.connector.Error as e:case['following_query']=error(e)
  finally:
   if c:
    try:c.close()
    except Exception as e:case['connection_close']=error(e)
   if db:
    try:db.close()
    except Exception as e:case['owner_close']=error(e)
   case['elapsed_seconds']=time.monotonic()-start;result['runs'].append(case);print(variant,size,case['result'],case.get('error'),case['following_query'],flush=True)
   (w/'evidence/frame-results.json').write_text(json.dumps(result,indent=2)+'\n')
def comparable(r):
 r={k:v for k,v in r.items() if k not in ['variant','elapsed_seconds']}
 for k in ['error','following_query','connection_close','owner_close']:
  if isinstance(r.get(k),dict):r[k]={x:y for x,y in r[k].items() if x!='message'}
 return r
result['differences']=[]
for size in [r['payload_bytes'] for r in result['runs'] if r['variant']=='baseline']:
 vals=[comparable(r) for r in result['runs'] if r['payload_bytes']==size]
 if vals[0]!=vals[1]:result['differences'].append(size)
result['comparison']='FAIL' if result['differences'] else 'PASS';(w/'evidence/frame-results.json').write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(int(bool(result['differences'])))
