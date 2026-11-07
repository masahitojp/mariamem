"""Execute unchanged owner tests against source mutations in owned disposable copies."""
import argparse, importlib.util, json, subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve()
here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('p1_baseline',here/'probe_baseline.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root=here.parents[2]
source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();m.base.identity(root,source_commit)
source=(root/'internal/nativewire/owner.go').read_text();tests=(root/'internal/nativewire/owner_test.go').read_bytes()
mutations={
 'ignores_native_completion':('l.native && l.relays == Reader|Writer','l.relays == Reader|Writer'),
 'ignores_reader_join':('l.relays == Reader|Writer','l.relays&Writer != 0'),
 'ignores_writer_join':('l.relays == Reader|Writer','l.relays&Reader != 0'),
 'releases_uncertain_open':('l.relays == Reader|Writer && l.state != uncertain','l.relays == Reader|Writer'),
 'ignores_opened_identity':('!o.current(l) || l.token != t {','!o.current(l) {'),
 'ignores_capture_open':('l.state == reserved || l.state == opening || l.state == uncertain','l.state == uncertain'),
 'wraps_requests_again':('if n == math.MaxUint32 {','if false {'),
}
dest=w/'temp/owner-controls';dest.mkdir(exist_ok=True);(dest/'go.mod').write_text('module ownercontrols\n\ngo 1.26.0\n');(dest/'owner_test.go').write_bytes(tests)
env=m.go_env(w);env['CGO_ENABLED']='1';rows=[]
for name,change in [('positive',None),*mutations.items()]:
 text=source
 if change:
  before,after=change
  if text.count(before)!=1:raise ValueError('mutation anchor changed: '+name)
  text=text.replace(before,after)
 (dest/'owner.go').write_text(text)
 command=['go','test','-race','-count=1','-timeout=30s','.']
 result=subprocess.run(command,cwd=dest,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
 (w/'evidence'/('owner-control-'+name+'.txt')).write_text(result.stdout)
 if (result.returncode==0)!=(change is None):raise ValueError('owner mutation detection failed: '+name)
 if change and '--- FAIL: Test' not in result.stdout:raise ValueError('mutation did not fail an assertion: '+name)
 rows.append({'name':name,'exit':result.returncode,'expected':'PASS' if change is None else 'FAIL','assertion_detected':change is not None})
(w/'evidence/owner-controls.json').write_text(json.dumps({'tooling_source_commit':source_commit,'source_sha256':m.base.sha(root/'internal/nativewire/owner.go'),'test_sha256':m.base.sha(root/'internal/nativewire/owner_test.go'),'cases':rows},indent=2)+'\n')
print('PASS positive and',len(mutations),'detected source mutations')
