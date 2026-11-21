"""Separate startup/fixture costs from the synchronized P8 SQL interval."""
import hashlib,json,os,platform,subprocess,sys
from pathlib import Path
W=Path(sys.argv[1]).resolve();part=sys.argv[2];p=W/'evidence/published';out=p/'runs';out.mkdir(exist_ok=True)
exe=W/'temp/perf'; env=dict(os.environ,GOMAXPROCS='8',GOGC='100',TMPDIR=str(W/'temp/gotmp'))
works=['A','B','C','mixed','large']
if part=='pre':
    meta=dict(host=platform.platform(),cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
              go=subprocess.check_output(['go','version','-m',exe],text=True),binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
              gomaxprocs=8,gogc=100)
    (p/'environment.json').write_text(json.dumps(meta,indent=2)+'\n')
for block in ([0] if part=='pre' else range(1,7)):
    order=works[block%5:]+works[:block%5]
    for work in order:
        for mode in (('os','both') if (block+works.index(work))%2==0 else ('both','os')):
            tag=f'{block}-{work}-{mode}'
            waves=1 if not block else 6
            r=subprocess.run([exe,'-work',work,'-waves',str(waves)],capture_output=True,text=True,env=dict(env,MARIAMEM_BENCH_STREAM=mode),timeout=120)
            (out/(tag+'.jsonl')).write_text(r.stdout)
            if r.returncode:
                (out/(tag+'.stderr')).write_text(r.stderr)
                raise RuntimeError(tag+' '+r.stderr[:1600])
            rows=[json.loads(s) for s in r.stdout.splitlines()]
            assert len(rows)==waves and all(x['wave']==i and x['workers']==8 and x['all_workers_closed'] for i,x in enumerate(rows))
            print(tag,flush=True)
