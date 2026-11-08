"""Reduce the successful actual-C-guest receipt; validate source/inventory before reduction."""
from pathlib import Path
import argparse,copy,hashlib,json,subprocess,sys
S=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(S/'benchmarks/lexercandidate'))
from codec import read
HOST='6134274a268155379329d9bd1ae394897e1f7e8e'
C='b1a265cc30a8603ced743c8aeb59c752751ff9d6'
G='14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1'
RUN=42437059943
NAMES=['macos','ubuntu']
PREFIXES=[('/'.join(['','Users','runner']),'<RUNNER_HOME>'),('/'.join(['','home','runner']),'<RUNNER_HOME>')]
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def norm(s):
 for old,new in PREFIXES:s=s.replace(old,new)
 return s
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--metadata',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 old=read(S/'benchmarks/lexerbinding/ci-42433100335/guest-record.json')
 assert old['source_identity']['commit']==C and old['guest_sha256']==G
 # Prior C-origin receipt retains the verified full Git source inventory. Only
 # changed paths are read from the exact host commit; a later working tree is irrelevant.
 host=copy.deepcopy(old['source_identity']['files_sha256'])
 names=subprocess.check_output(['git','diff','--name-only',C,HOST],cwd=S,text=True).splitlines()
 host_names=set(subprocess.check_output(['git','ls-tree','-r','--name-only',HOST],cwd=S,text=True).splitlines())
 for name in names:
  if name in host_names:host[name]=sha(subprocess.check_output(['git','show',HOST+':'+name],cwd=S))
  else:host.pop(name,None)
 assert set(host)==host_names
 run=json.loads((a.metadata/'run.json').read_text());assert run['id']==RUN and run['head_sha']==HOST and run['conclusion']=='success'
 jobs=json.loads((a.metadata/'jobs.json').read_text())['jobs'];assert len(jobs)==2 and all(j['conclusion']=='success' for j in jobs)
 for name in ['run.json','jobs.json','artifacts.json','artifacts-verified.json']:(a.output/name).write_bytes((a.metadata/name).read_bytes())
 summaries={};provenance={};normalization={};originals={}
 for h in NAMES:
  root=a.input/h; checks=json.loads((root/'SHA256SUMS.json').read_text())
  assert set(checks)=={str(q.relative_to(root)) for q in root.rglob('*') if q.is_file()}-{'SHA256SUMS.json'}
  for name,digest in checks.items():assert sha((root/name).read_bytes())==digest,(h,name)
  d=json.loads((root/'development.json').read_text());r=json.loads((root/'result.json').read_text());sql=json.loads((root/'sql.json').read_text())
  assert d['source_identity']==old['source_identity']
  assert d['host_source_identity']=={'commit':HOST,'files_sha256':host}
  assert d['guest_sha256']==r['guest_sha256']==G and r['host_source_commit']==sql['source_commit']==HOST and r['c_source_commit']==C
  assert r['result']=='PASS_ACTUAL_C_GUEST' and d['smoke']=='PASS' and d['result']=='UNQUALIFIED'
  assert sql['result']=='PASS_GUEST' and sql['children']==2 and sql['cleanup_errors']==[]
  assert sql['cleanup']==dict(refs=0,process_exit=0,reaped=True,root_exists=False)
  assert sql['host_sha256']==r['host_sha256']==d['binary_sha256']
  assert len(r['commands'])==5 and all(c['exit_code']==0 for c in r['commands'])
  join=json.loads((root/'join/results.json').read_text());assert len(join)==6 and all(x['passed'] for x in join)
  assert sum(x['expected_failure'] for x in join)==2 and all(x['exit_code']==int(x['expected_failure']) for x in join)
  expected={k:v for k,v in host.items() if not k.startswith('internal/generatedgo/')}
  expected.update({'internal/generatedgo/'+k:v for k,v in d['generated_inventory'].items()})
  kind=subprocess.check_output(['git','show',HOST+':internal/runtimekind/kind.go'],cwd=S)
  baseline=json.loads(subprocess.check_output(['git','show',HOST+':release/generated-go-inputs.json'],cwd=S))['guest_sha256']
  old_kind=('const GuestSHA256 = "'+baseline+'"').encode();assert kind.count(old_kind)==1
  expected['internal/runtimekind/kind.go']=sha(kind.replace(old_kind,('const GuestSHA256 = "'+G+'"').encode()))
  assert expected==d['host_source_inventory']
  original=copy.deepcopy(d)
  for key in ['source_identity','host_source_identity']:
   value=d[key];d[key]={'commit':value['commit'],'files':len(value['files_sha256']),'files_sha256_canonical_digest':sha(canonical(value['files_sha256']))}
  d['host_source_inventory']={'files':len(expected),'files_sha256_canonical_digest':sha(canonical(expected))}
  d['reduction']={'original_sha256':sha((root/'development.json').read_bytes()),'source_inventory_validation':'EXACT_MATCH_TO_PINNED_GIT_AND_REGENERATED_RUNTIME','recipe':'benchmarks/lexerbinding/preserve_host.py; prior C receipt full source inventory plus git diff C..HOST, exact staged runtime inventory and one guest identity replacement'}
  # Actual logs and bounded gate results survive; duplicate source inventories
  # are replaced by derivable canonical digests after exact equality checks.
  for q in root.rglob('*'):
   if not q.is_file() or q.name=='development.json':continue
   name=str(q.relative_to(root));published=norm(q.read_text());target=a.output/h/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(published)
   originals[h+'/'+name]={'original_sha256':sha(q.read_bytes()),'published_sha256':sha(target.read_bytes())}
  write(a.output/h/'development-reduced.json',json.loads(norm(json.dumps(d))))
  provenance[h]=original
  summaries[h]={'result':r['result'],'job':next(j['id'] for j in jobs if ('macos' if h=='macos' else 'ubuntu') in j['name']),
     'platform':r['platform'],'machine':r['machine'],'host_sha256':d['binary_sha256'],
     'gates':{'dev_smoke':'PASS','full_638_tables':'PASS','corrupt_table':'PASS','worker_trap':'PASS','crc':'PASS','J1':{'expected_failures_detected':2,'protected_successes':4},'native_sql_two_children':'PASS','cleanup':'PASS'}}
 m,u=provenance['macos'],provenance['ubuntu'];diff=[k for k in set(m['generated_inventory'])|set(u['generated_inventory']) if m['generated_inventory'].get(k)!=u['generated_inventory'].get(k)]
 assert diff==['provenance.json']
 assert m['raw_translation']['files_sha256']==u['raw_translation']['files_sha256']
 assessment={'run':RUN,'host_source_commit':HOST,'c_source_commit':C,'guest_sha256':G,'result':'PASS_BOUNDED_ACTUAL_C_GUEST','hosts':summaries,'raw_files_identical':51,'installed_files_identical_excluding_provenance':108,'provenance_difference':'host-specific installation paths/converter binary; no runtime source byte difference','performance':'NOT_MEASURED_FOR_C_GUEST','independent_c_builds':1,'qualification':'NOT_RUN','adoption':'NOT_APPROVED'}
 write(a.output/'assessment.json',assessment)
 write(a.output/'normalization.json',{'prefixes':[{'original_parts':['','Users','runner'],'published':'<RUNNER_HOME>'},{'original_parts':['','home','runner'],'published':'<RUNNER_HOME>'}],'files':originals,'development_records':'Source inventories reduced only after exact validation; original file hashes remain in artifacts-verified.json and development-reduced.json'})
 write(a.output/'SHA256SUMS.json',{str(q.relative_to(a.output)):sha(q.read_bytes()) for q in sorted(a.output.rglob('*')) if q.is_file()})
 print(json.dumps(assessment,indent=2))
if __name__=='__main__':main()
