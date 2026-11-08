"""Exercise the real installer rejection gates for the exact new guest binding."""
import json,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[3];variant=sys.argv[1];w=R/'build/issue128-real/temp/runtime'/variant;out=w/'temp/host';repo=w/'worktree';base=json.loads((w/'evidence/reviewed-binding/identity.json').read_text());results={}
for name in ['body-digest','ABI-offset']:
 pin=json.loads(json.dumps(base))
 if name=='body-digest':next(iter(pin['functions'].values()))['normalized_sha256']='0'*64
 else:pin['ABI_offsets']['pthread.map_size']=48
 p=w/'temp'/('negative-'+name+'.json');p.write_text(json.dumps(pin))
 command=[sys.executable,str(repo/'scripts/generate_runtime.py'),'--source-module',str(out/'candidate/module'),'--development-input',str(out/'installation-inputs.json'),'--development-thread-binding',str(p),'--output',str(w/'temp'/('negative-'+name))]
 r=subprocess.run(command,capture_output=True,text=True,timeout=60)
 (w/'evidence'/('negative-'+name+'.txt')).write_text(r.stdout+r.stderr)
 expected='experimental exact worker function changed' if name=='body-digest' else 'experimental worker binding identity/ABI mismatch'
 assert r.returncode!=0 and expected in r.stderr,(name,r.returncode,r.stderr[-2000:])
 results[name]={'rejected':True,'exit':r.returncode,'expected_error':expected,'mutation':'reviewed expected function digest' if name=='body-digest' else 'ABI map_size44 to48','generated_runtime_was_not_compiled':True}
(w/'evidence/binding-negatives.json').write_text(json.dumps(results,indent=2)+'\n');print(results)
