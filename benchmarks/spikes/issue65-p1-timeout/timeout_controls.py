"""Execute unchanged duration tests against four focused source mutations."""
import argparse,importlib.util,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve();here=Path(__file__).resolve().parent;root=here.parents[2]
spec=importlib.util.spec_from_file_location('timeout_baseline',here/'probe_baseline.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();m.base.identity(root,source_commit)
source=(root/'internal/nativewire/timeout.go').read_text();tests=(root/'internal/nativewire/timeout_test.go').read_bytes()
mutations={
 'wrong_default':('d = 30 * time.Second','d = 10 * time.Second'),
 'rounds_milliseconds':('return uint64(d), nil','return uint64(d/time.Millisecond)*uint64(time.Millisecond), nil'),
 'rejects_submillisecond':('if d < 0 {','if d < 100*time.Millisecond {'),
 'fixture_multiply_overflow':('if ms > uint64(math.MaxInt64)/uint64(time.Millisecond) {','if ms > uint64(math.MaxInt64) {'),
}
dest=w/'temp/timeout-controls';dest.mkdir(exist_ok=True);(dest/'go.mod').write_text('module timeoutcontrols\n\ngo 1.26.0\n');(dest/'timeout_test.go').write_bytes(tests)
env=m.go_env(w);env['CGO_ENABLED']='1';rows=[]
for name,change in [('positive',None),*mutations.items()]:
 text=source
 if change:
  before,after=change
  if text.count(before)!=1:raise ValueError('timeout mutation seam changed: '+name)
  text=text.replace(before,after)
 (dest/'timeout.go').write_text(text)
 r=subprocess.run(['go','test','-race','-count=1','-timeout=30s','.'],cwd=dest,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
 (w/'evidence'/('timeout-control-'+name+'.txt')).write_text(r.stdout)
 if (r.returncode==0)!=(change is None):raise ValueError('timeout mutation not detected: '+name)
 if change and '--- FAIL: Test' not in r.stdout:raise ValueError('timeout mutation failed without an assertion: '+name)
 rows.append({'name':name,'exit':r.returncode,'expected':'PASS' if change is None else 'FAIL'})
(w/'evidence/timeout-controls.json').write_text(json.dumps({'tooling_source_commit':source_commit,'source_sha256':m.base.sha(root/'internal/nativewire/timeout.go'),'test_sha256':m.base.sha(root/'internal/nativewire/timeout_test.go'),'cases':rows},indent=2)+'\n');print('PASS duration/race and4 detected source mutations')
