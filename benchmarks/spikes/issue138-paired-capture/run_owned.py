"""Reuse the existing disk/process guard, exporting measured stage costs."""
import json,os,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R/'scripts'))
from experiment_disk import DiskGuard,run_guarded
name,timeout=sys.argv[1],float(sys.argv[2]);args=sys.argv[3:];start=time.monotonic()
guard=DiskGuard(R,12,12) # Conservative: includes tracked checkout and all owned caches.
out=R/'build/issue128-real/temp';out.mkdir(parents=True,exist_ok=True)
os.environ['TMPDIR']=str(out/'common-tmp');Path(os.environ['TMPDIR']).mkdir(exist_ok=True)
os.environ['GOTMPDIR']=os.environ['TMPDIR'];os.environ['PYTHONDONTWRITEBYTECODE']='1'
code=None;error=None
try:
 with (out/(name+'.txt')).open('w') as stream:code=run_guarded(args,guard,timeout=timeout,interval=2,output=stream)
except BaseException as e:error={'type':type(e).__name__,'message':str(e)};raise
finally:
 (out/(name+'.json')).write_text(json.dumps({'command':args,'exit':code,'error':error,'wall_seconds':time.monotonic()-start,'peak_conservatively_owned_bytes':guard.peak,'minimum_free_bytes':guard.minimum_free,'scope':'entire assigned checkout including all host/container mounts, source, SDK, caches, temp, output'},indent=2)+'\n')
raise SystemExit(code)
