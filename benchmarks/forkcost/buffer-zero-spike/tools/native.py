from pathlib import Path
import os,subprocess,json,sys
E=Path(__file__).resolve().parent;X=E.parent;W=X/'worktree';T=X/'temp';env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'),MARIAMEM_PHASE_TRACE=str(E/'native-phases.jsonl'))
cmd=[str(T/'venv/bin/python'),str(W/'scripts/regenerate_release_guest.py'),'--development','--guest-dir',str(T/'guest'),'--output',str(T/'native')];(E/'native-command.json').write_text(json.dumps({'argv':cmd,'timeout_seconds':2700},indent=2))
with (E/'native-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=2700,check=True)
print('PASS isolated UNQUALIFIED native regeneration and SQL/Snapshot/Fork smoke',flush=True)
