import json, subprocess, os, hashlib
from pathlib import Path
w=Path(__file__).resolve().parents[1]; ev=w/'evidence'; tools=w/'temp/tools'; binary=w/'temp/ownedprepared'
records=[]
for p in sorted(ev.glob('*.cpu')):
    out=p.with_suffix('.cpu-top.txt')
    cmd=[str(tools/'pprof'),'-top','-nodecount=35',str(binary),str(p)]
    r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
    out.write_text(r.stdout); records.append({'command':cmd,'returncode':r.returncode})
    assert r.returncode==0
    for focus in ['runtime\.(gc|scan|mark|sweep|madvise|memclr|memmove|malloc|sysUnused|sysUsed)','runtime\.(gc|scan|mark|sweep)']:
        name='runtime-memory' if 'madvise' in focus else 'gc'
        cmd=[str(tools/'pprof'),'-top','-nodecount=25','-focus='+focus,str(binary),str(p)]
        r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
        p.with_suffix('.'+name+'.txt').write_text(r.stdout);records.append({'command':cmd,'returncode':r.returncode}); assert r.returncode==0
for p in sorted(ev.glob('*.trace')):
    for kind in ['sync','net','syscall','sched']:
        prof=p.with_suffix('.'+kind+'.pprof')
        cmd=[str(tools/'trace'),'-pprof='+kind,str(p)]
        with prof.open('wb') as out:
            r=subprocess.run(cmd,stdout=out,stderr=subprocess.PIPE,timeout=120)
        records.append({'command':cmd,'returncode':r.returncode,'stderr':r.stderr.decode()});assert r.returncode==0
        cmd=[str(tools/'pprof'),'-top','-nodecount=25',str(prof)]
        r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
        p.with_suffix('.'+kind+'-top.txt').write_text(r.stdout);records.append({'command':cmd,'returncode':r.returncode});assert r.returncode==0
(ev/'profile-reduction.json').write_text(json.dumps(records,indent=2))
print('Profile reduction complete')
