"""P8 matched quartets. Never start another timed child while the last is alive."""
from pathlib import Path
import collections,csv,gzip,json,os,resource,shutil,subprocess,sys,time
w=Path(sys.argv[1]).resolve()
t=w/'temp';out=w/'evidence/published';run_dir=out/'runs';run_dir.mkdir(exist_ok=True)
sys.path.insert(0,str(w/'worktree/scripts'))
from experiment_disk import DiskGuard
guard=DiskGuard(w,min_free_gib=8,budget_gib=8)
cases='GetOrder ListOrders SearchProducts TopProducts RevenueByCategory CreateOrder ApplyDiscount DeleteUser ShipOrder CancelOrder'.split()
stages='Call Queue Write Input Worker Reply Output Header Body Notify Resume'.split()
def gzip_json(path,data):
    with gzip.open(path,'wt',compresslevel=4) as f: json.dump(data,f,separators=(',',':'))

def run(arm,block,pos,series,sem=False):
    label=f'{series}-{block:02}-{pos}-{arm}'; exe=t/(arm.replace('light','diag')+'.test')
    diag=not arm.startswith('raw')
    env={k:os.environ[k] for k in ('PATH','HOME') if k in os.environ}
    path=t/(label+'.suite')
    env.update(TMPDIR=str(t/'gotmp'),GOMAXPROCS='8',GOGC='100',MODELCASE_MATCHED='1',
               MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0',SKIP_READ_BODY='0',
               TRANSPORT_DIAG='0',MODELCASE_TRACE=str(path),P8_REQUESTS=str(t/(label+'.req')),P8_CLIENTS=str(t/(label+'.client')))
    pattern='^TestMatchedSemantics$' if sem else '^Test('+'|'.join(cases)+')$'
    args=[exe,'-test.run='+pattern,'-test.parallel=8','-test.timeout=60s','-test.v']
    trace=t/(label+'.trace')
    if arm.startswith('diag') and not sem:args+=['-test.trace='+str(trace)]
    cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
    proc=subprocess.run(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=75)
    end=resource.getrusage(resource.RUSAGE_CHILDREN)
    log=proc.stdout.decode(errors='replace')
    (t/(label+'.log')).write_text(log)
    if proc.returncode or '--- SKIP:' in log:raise RuntimeError(label+' '+log[-2500:])
    suite=json.loads(path.read_text())
    if sem:
        assert '--- PASS: TestMatchedSemantics ' in log
        return
    spans=suite['spans']
    counts=collections.Counter(s['kind'] for s in spans)
    assert all(counts[k]==v for k,v in dict(sample=21,fork=21,write=20,read=50).items())
    samples=[s for s in spans if s['kind']=='sample']
    tails=[s for s in samples if s['end_ms']-s['start_ms']>=400]
    record=dict(arm=arm,series=series,block=block,position=pos,suite=suite,
        cpu_ms=1000*(end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime))
    if diag:
        req=json.loads(Path(env['P8_REQUESTS']).read_text())
        clients=json.loads(Path(env['P8_CLIENTS']).read_text())
        assert set(clients)=={s['lane'] for s in samples} and set(req)==set(clients)|{'root'}
        record['clients']=clients
        # Drop root setup rows from compact storage after validating every response.
        for lane,rows in req.items():
            for key,row in rows.items():
                assert int(key)==row['ID'] and row['N']>=13
                times=[row[k] for k in stages if k not in ('Worker','Reply') or row[k]]
                assert all(times) and times==sorted(times),(label,lane,key,row)
        record['request_columns']=['ID','Slot','Op','N']+stages
        record['requests']={lane:[[r[k] for k in record['request_columns']] for r in rows.values()]
                            for lane,rows in req.items() if lane!='root'}
        for lane,ops in clients.items():
            assert collections.Counter(o['Op'] for o in ops)==dict(begin=1,prepare_order=1,prepare_item=1,prepare_stock=1,
                order=40,item=100,stock=100,commit=1),(label,lane,len(ops))
            assert all(o['End']>=o['Start']>0 for o in ops)
        if trace.exists() and tails:
            print('retaining trace',label,[s['lane'] for s in tails],flush=True)
        elif trace.exists():
            trace.unlink()
    gzip_json(run_dir/(label+'.json.gz'),record)
    print(label,round(suite['elapsed_ms'],1),round(max(s['end_ms']-s['start_ms'] for s in samples),1),len(tails),flush=True)
    return len(tails)

if __name__=='__main__':
    arms=['raw-os','raw-ring','diag-os','diag-ring']
    if sys.argv[2:] == ['pilot']:
        for arm in arms:
            guard.check()
            run(arm,0,0,'semantic',True)
            run(arm,0,0,'warm')
        sys.exit()
    assert len(list(run_dir.glob('warm-*.gz')))==4
    orders=[[0,1,3,2],[1,2,0,3],[2,3,1,0],[3,0,2,1]]
    tails=0
    for i in range(24):
        guard.check()
        for pos,j in enumerate(orders[i%4]):
            n=run(arms[j],i+1,pos,'primary')
            if arms[j].startswith('diag'):tails+=n
    if not tails:
        for i in range(16):
            guard.check()
            for pos,j in enumerate([0,1] if i%2==0 else [1,0]):
                run(['light-os','light-ring'][j],i+1,pos,'light')
    print(guard.check(),flush=True)
