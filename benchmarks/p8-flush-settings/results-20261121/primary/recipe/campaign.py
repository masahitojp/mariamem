"""Matched P8 runs, no execution tracing. Store all slow waits and sample windows."""
import csv,gzip,itertools,json,os,re,resource,subprocess,sys
from decimal import Decimal
from collections import Counter
from pathlib import Path
w=Path(sys.argv[1]).resolve()
out=w/'evidence/published';t=w/'temp';dest=out/'runs';dest.mkdir(exist_ok=True)
sys.path.insert(0,str(w/'worktree/scripts'))
from experiment_disk import DiskGuard
guard=DiskGuard(w,min_free_gib=8,budget_gib=8)
names='GetOrder ListOrders SearchProducts TopProducts RevenueByCategory CreateOrder ApplyDiscount DeleteUser ShipOrder CancelOrder'.split()
def run(arm,block,pos,kind):
    label=f'{kind}-{block:03}-{pos}-{arm}'
    env={k:os.environ[k] for k in ('HOME','PATH') if k in os.environ}
    env.update(FLUSH_MODE=arm,TMPDIR=str(t/'gotmp'),GOGC='100',GOMAXPROCS='8',MODELCASE_MATCHED='1',REVENUE_PREAGG='1',
               MARIA_AUDIT_OF='1',MARIA_ASYNC_CLOSE='0',SKIP_READ_BODY='0',TRANSPORT_DIAG='0',
               P8_CLIENTS=str(t/'clients.json'),FUTEX_OUT=str(t/'futex.json'),MODELCASE_TRACE=str(t/'suite.json'))
    pattern='^TestMatchedSemantics$' if kind=='meaning' else '^Test('+'|'.join(names)+')$'
    cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
    p=subprocess.run([t/'diag-ring.test','-test.run='+pattern,'-test.parallel=8','-test.v','-test.timeout=60s'],
                     env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=75)
    end=resource.getrusage(resource.RUSAGE_CHILDREN);log=p.stdout.decode(errors='replace')
    if p.returncode or '--- SKIP' in log:
        (w/'evidence'/('failed-'+label+'.log')).write_text(log)
        raise RuntimeError(label+' '+log[-2200:])
    settings={}
    for lane, mode, before, after in re.findall(r'^FLUSH_CONFIG (\S+) (\S+) \[(.*?)\] \[(.*?)\]$',log,re.M):
        assert mode==arm and lane not in settings
        before,after=before.split(),after.split()
        assert len(before)==len(after)==7
        expected=before.copy()
        if arm=='early':
            assert Decimal(before[0])!=Decimal('0.001') and Decimal(after[0])==Decimal('0.001'),(before,after)
            expected[0]=after[0]
        if arm=='capacity':
            assert before[1]!='1000'
            expected[1]='1000'
        assert expected==after,(arm,expected,after)
        settings[lane]={'before':before,'after':after}
    assert len(settings)==(1 if kind=='meaning' else 21),(arm,log[-800:],settings)
    assert len({tuple(v['after']) for v in settings.values()})==1
    if kind=='meaning':print(settings,flush=True)
    if kind=='meaning':
        assert '--- PASS: TestMatchedSemantics ' in log;print(label,'PASS',flush=True);return
    suite=json.loads((t/'suite.json').read_text());dbs=json.loads((t/'futex.json').read_text())
    clients=json.loads((t/'clients.json').read_text());sp=suite['spans'];s=count=Counter(row['kind'] for row in sp)
    assert all(s[k]==v for k,v in dict(fork=21,sample=21,read=50,write=20).items())
    for i,name in enumerate(names):
        assert sum(x['kind'] in ('read','write') and x['lane'].startswith('Test'+name+'/') for x in sp)==(10 if i<5 else 4)
    samples=[r for r in sp if r['kind']=='sample'];assert set(clients)=={s['lane'] for s in samples} and set(dbs)==set(clients)|{'root'}
    stacks=[];indexes={}
    def intern(frames):
        if not frames:return None
        key=tuple(frames)
        if key not in indexes:indexes[key]=len(stacks);stacks.append(frames)
        return indexes[key]
    origin=int(suite['meta']['probe_ns']);windows={}
    for r in samples:
        lane=r['lane'];a=origin+round(r['start_ms']*1e6);b=origin+round(r['end_ms']*1e6)
        windows[lane]={'start':a,'end':b}
        ops=clients[lane]; assert Counter(o['Op'] for o in ops)==dict(begin=1,prepare_order=1,prepare_item=1,prepare_stock=1,order=40,item=100,stock=100,commit=1)
        assert all(o['Start']>=a-2000 and o['End']<=b+2000 and o['Start']<=o['End'] for o in ops)
        # Save client operations for every slow sample and both edges of a long wait otherwise.
        if b-a>=400_000_000:windows[lane]['operations']=ops
    for lane,db in dbs.items():
        token=set()
        for ev in db['events'] or []:
            assert ev['Token'] not in token and ev['Selected']-ev['Start']>=100_000_000
            token.add(ev['Token'])
            if ev['Branch']=='notify':assert ev['Start']<=ev['Notified']<=ev['Selected']
            elif ev['Branch']=='timeout':assert ev['Timeout']>=0
            else:assert ev['Branch']=='failure'
            ev['WaitStack']=intern(ev['WaitStack']);ev['WakeStack']=intern(ev['WakeStack'])
            q=ev['Host']
            if q:
                assert q['ID']==ev['Waiting']['Request'] and q['Slot']==q['ReplySlot']
                assert q['Call']<=ev['Waiting']['WorkerAt']<=ev['Start']<=ev['Selected']<=q['Reply']<=q['Resume'],(label,lane,q,ev)
                ops=clients.get(lane,[])
                match=[(i,o) for i,o in enumerate(ops) if o['Start']<=ev['Start'] and ev['Selected']<=o['End']]
                if match:
                    assert len(match)==1
                    ev['ClientIndex'],ev['ClientOp']=match[0]
    long=[lane for lane,r in windows.items() if r['end']-r['start']>=400_000_000]
    assert settings.keys()==windows.keys()
    data=dict(settings=settings,arm=arm,block=block,position=pos,kind=kind,windows=windows,dbs=dbs,stacks=stacks,
              cpu_ms=1000*(end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime),suite_ms=suite['elapsed_ms'],counts=dict(count))
    with gzip.open(dest/(label+'.json.gz'),'wt') as f:json.dump(data,f,separators=(',',':'))
    print(label,round(suite['elapsed_ms'],1),long,flush=True)
if __name__=='__main__':
    arms=('default','early','capacity') if len(sys.argv)<4 else tuple(sys.argv[3].split(','))
    if sys.argv[2]=='pilot':
        for arm in arms:
            guard.check();run(arm,0,0,'meaning');run(arm,0,0,'warm')
    else:
        orders=list(itertools.permutations(arms))
        for i in range(1,97):
            guard.check()
            for pos,arm in enumerate(orders[(i-1)%len(orders)]):run(arm,i,pos,'main')
        print(guard.check(),flush=True)
