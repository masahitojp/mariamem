"""Run fresh processes, using six permutations of two OS controls and the ring."""
import csv,itertools,os,re,subprocess,sys
from pathlib import Path
w=Path.cwd()
out=w/'evidence'
sizes=[8192,16384,32768,65536,262144]
def measure(arm,size,block,phase,n=1):
    executable='os' if arm=='os2' else arm
    env=dict(os.environ,GOMAXPROCS='8',GOGC='100',PAYLOAD=str(size))
    if phase=='profile':
        env['PROFILE']=str(out/(arm+'.pprof'))
    args=[w/'temp'/executable,'-test.run=^$','-test.bench=^BenchmarkLargeResponseBatch$','-test.benchtime='+str(n)+'x','-test.count=1']
    # testing runs a 1x calibration before fixed Nx; profile is replaced on final invocation.
    log=subprocess.check_output(args,cwd=w/'worktree',env=env,text=True,stderr=subprocess.STDOUT,timeout=200)
    assert 'PASS' in log,log
    line=next(l for l in log.splitlines() if re.match(r'BenchmarkLargeResponseBatch-8\s+',l))
    tokens=line.split()
    row=dict(arm=arm,size=size,block=block,n=int(tokens[1]))
    row.update({k:float(v) for v,k in zip(tokens[2::2],tokens[3::2])})
    assert row['n']==n and row['cpu-ns/op']>0
    path=out/(phase+'.csv')
    with path.open('a') as f:
        writer=csv.DictWriter(f,fieldnames=row,lineterminator="\n")
        if f.tell()==0:writer.writeheader()
        writer.writerow(row)
if __name__=='__main__':
    phase=sys.argv[1]
    assert not (out/(phase+'.csv')).exists()
    if phase=='perf':
        for block,order in enumerate(itertools.permutations(('os','ring','os2')),1):
            for size in sizes if block%2 else reversed(sizes):
                for arm in order:measure(arm,size,block,phase)
            print(block,flush=True)
    if phase=='diag':
        for size in sizes:
            for arm in ('os-diag','ring-diag'):measure(arm,size,1,phase)
    if phase=='profile':
        for arm in ('os','ring'):measure(arm,262144,1,phase,80)
