from pathlib import Path
import copy,json,subprocess,sys
w=Path('.').resolve();repo=w/'worktree';profile=json.loads((w/'temp/tools/binding.json').read_text());rows=[]
for name in ['wrong_guest','wrong_function_hash']:
 p=copy.deepcopy(profile)
 if name=='wrong_guest':p['guest_sha256']='0'*64;expected='identity/ABI mismatch'
 else:
  free=next(x for x in p['functions'].values() if x['role']=='free');free['normalized_sha256']='0'*64;expected='exact worker function changed'
 path=w/'temp'/('guard-'+name+'.json');path.write_text(json.dumps(p));out=w/'temp'/('guard-'+name)
 result=subprocess.run([sys.executable,str(repo/'scripts/generate_runtime.py'),'--source-module',str(w/'temp/host/candidate/module'),'--development-input',str(w/'temp/host/installation-inputs.json'),'--development-thread-binding',str(path),'--output',str(out)],capture_output=True,text=True)
 assert result.returncode!=0 and expected in result.stderr,(name,result.returncode,result.stderr[-1000:])
 (w/'evidence'/('guard-'+name+'.txt')).write_text(result.stdout+result.stderr)
 rows.append({'control':name,'exit_code':result.returncode,'expected_rejection_observed':True})
(w/'evidence/development-binding-controls.json').write_text(json.dumps(rows,indent=2)+'\n');print(rows)
