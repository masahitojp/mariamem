"""Observe #95's two Prisma cases independently from #94 pipeline acceptance."""
import argparse,contextlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--prisma',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--native-port',type=int);p.add_argument('--host',type=Path);a=p.parse_args()
sys.path[:0]=[str(a.source/'python'),str(a.source/'scripts')]
import mariamem
from git_identity import verify_go_binary
spec=importlib.util.spec_from_file_location('previous',a.prisma/'matrix.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r={'scope':'ISSUE95_TWO_PRISMA_CASES_NOT_FULL_PIPELINE_ACCEPTANCE','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.source,text=True).strip(),'prisma_source_commit':'604a0c588f0a602bf6ea67d811b97bae2748c3ea','cells':[]}
if a.host:r['binary_build_info']=verify_go_binary(a.source,a.host,r['source_commit'])
@contextlib.contextmanager
def endpoint():
 if a.host:
  with mariamem.start(host_binary=a.host) as db:yield db.connection_info()
 else:yield dict(host='127.0.0.1',port=a.native_port,user='root',password='')
for off in ((False,True) if a.host else (False,)):
 for name in ('nested_create','unique_error'):
  with endpoint() as info:
   if a.native_port:m.sql(info,'DROP DATABASE IF EXISTS prisma_matrix')
   m.initialize(info,True)
   p=subprocess.run(['node','--import','tsx','matrix.ts',name],cwd=a.prisma,env=m.env_for(info,off),capture_output=True,text=True,timeout=45)
   r['cells'].append({'name':name,'pipelining':not off,'exit_code':p.returncode,**m.last_json(p.stdout)})
r['summary']={k:sum(c.get('result')==k for c in r['cells']) for k in ('PASS','FAIL')}
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
