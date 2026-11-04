"""All 27 existing Client cases and Live Reset under the default Node pipeline."""
import importlib.util,json,os,re,subprocess,sys
from pathlib import Path
root=Path.cwd();w=root.parent;e=w/'evidence';project=w/'temp/prisma';host=w/'temp/mariamem-host'
sys.path[:0]=[str(root/'python'),str(root/'scripts')]
import mariamem
from git_identity import verify_go_binary
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();stamp=verify_go_binary(root,host,source)
spec=importlib.util.spec_from_file_location('prior',project/'matrix.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
os.environ['MARIAMEM_PIPELINE_SPIKE_TRACE']='1'
r={'scope':'EXPERIMENT_PIPELINING_TRUE_CLIENT27_AND_LIVE1','source_commit':source,'base_source_commit':'82f96435777079f38d01f5f2012eda3cb2329cda','issue93_overlay_only':True,'prisma_source_commit':'604a0c588f0a602bf6ea67d811b97bae2748c3ea','binary_build_info':stamp,'cells':[],'header_samples':[]}
assert not (e/'matrix-final').exists(), 'use a fresh output directory for a new run'
for name in m.RUNTIME:
 directory=e/'matrix-final'/name;directory.mkdir(exist_ok=True,parents=True);row={'name':name}
 try:
  with mariamem.start(host_binary=host,log_path=directory/'host.log') as db:
   info=db.connection_info();m.initialize(info,True);row['observed']=m.run_node(name,m.env_for(info,False),directory)
   observed_headers=(db._session.root/'host.log').read_text(errors='replace')
   for match in re.finditer(r'PIPELINE_SPIKE current=(\d+) next=(\d+) queued=(\d+) frame_bytes=(\d+) sequence=(\d+)',observed_headers):
    r['header_samples'].append({'case':name,**dict(zip(('current','next','queued','frame_bytes','sequence'),map(int,match.groups())))})
  row['result']='PASS'
 except Exception as err:row.update(result='FAIL',error=str(err))
 r['cells'].append(row)
 print(name,row['result'],str(row.get('error',''))[:180],flush=True)
 (e/'prisma-matrix.json').write_text(json.dumps(r,indent=2)+'\n')
directory=e/'matrix-final/live';directory.mkdir(exist_ok=True,parents=True);row={'name':'live-reset'}
try:row.update(result='PASS',observed=m.live_case(host,False,directory))
except Exception as err:row.update(result='FAIL',error=str(err))
r['cells'].append(row);r['summary']={k:sum(x['result']==k for x in r['cells']) for k in ('PASS','FAIL')}
(e/'prisma-matrix.json').write_text(json.dumps(r,indent=2)+'\n')
assert any(x['current']==22 and x['next']==23 for x in r['header_samples']),'did not observe EXECUTE queued before PREPARE response'
(e/'prisma-matrix.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r['summary']),flush=True)
