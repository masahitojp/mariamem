from pathlib import Path
import subprocess,signal,json,time
E=Path(__file__).resolve().parent;X=E.parent;repo=X.parents[2];name='mariamem-bp-zero-candidate'
def interrupted(sig,frame):raise InterruptedError(f'signal {sig}')
for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,interrupted)
mounts=[(X,'/exp',False),(X/'worktree','/exp/worktree',True),(X/'temp/build','/exp/worktree/build',False),(repo/'.git',str(repo/'.git'),True),(X/'temp/root','/root',False),(X/'temp/work','/work',False)]
cmd=['docker','run','--rm','--name',name,'--cpus','8']
for src,dst,ro in mounts:cmd+=['--mount',f'type=bind,src={src},dst={dst}'+(',readonly' if ro else '')]
cmd+=['-e','MARIAMEM_PHASE_TRACE=/exp/evidence/guest-phases.jsonl','3ded805d8dca','/usr/bin/python3','/exp/worktree/scripts/build_generated_guest.py','--development-output','/exp/temp/guest']
(E/'guest-command.json').write_text(json.dumps({'argv':cmd,'timeout_seconds':2700},indent=2))
start=time.time();ok=False
try:
 with (E/'guest-build.log').open('w') as out:subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=2700)
 ok=True
finally:
 subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 (E/'guest-completion.json').write_text(json.dumps({'success':ok,'elapsed_seconds':time.time()-start},indent=2))
