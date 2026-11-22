from pathlib import Path
import collections,gzip,json,os,subprocess,sys
w=Path.cwd();t=w/'temp';out=w/'evidence/runs'
names='GetOrder ListOrders SearchProducts TopProducts RevenueByCategory CreateOrder ApplyDiscount DeleteUser ShipOrder CancelOrder'.split()
def run(arm,role,b,i,p=1):
    tag=f'{role}-{b}-{i}-{arm}-p{p}'
    env={k:os.environ[k] for k in ('HOME','PATH')};env.update(GOMAXPROCS='8',GOGC='100',TMPDIR=str(t/'gotmp'),MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0',SKIP_READ_BODY='0',TRANSPORT_DIAG='0',MODELCASE_TRACE=str(t/(tag+'.json')),PHASES=str(t/(tag+'.phases')))
    sem=role=='sem'
    result=subprocess.run([t/(arm+'.test'),'-test.timeout=110s',f'-test.parallel={p}','-test.v','-test.run='+('^TestMatchedSemantics$' if sem else '^Test('+'|'.join(names)+')$')],env=env,capture_output=True,text=True,timeout=120)
    if result.returncode or '--- SKIP:' in result.stdout or 'PASS' not in result.stdout:
        (out/(tag+'.log')).write_text(result.stdout+result.stderr);raise RuntimeError(tag+' '+(result.stdout+result.stderr)[-1400:])
    data=json.loads((t/(tag+'.json')).read_bytes())
    if not sem:
        c=collections.Counter(s['kind'] for s in data['spans'])
        assert all(c[k]==n for k,n in dict(boot=1,snapshot=1,read=50,write=20,close=21,fork=21,sample=21).items())
    if arm.endswith('diag'):
        ds=list(map(json.loads,(t/(tag+'.phases')).read_text().splitlines()))
        assert len(ds)==21 and all(r[1]==[1,1,40,100,100,1,0] for r in ds)
        data['phase_ns']=[r[0] for r in ds]
    file=out/(tag+'.json.gz')
    assert not file.exists();file.write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
    print(tag,data['elapsed_ms'],flush=True)
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='base':
        for role in ('sem','warm'):
            for i,a in enumerate(('maria','pg')):run(a,role,0,i)
    for b in range(1,7):
        arms=('maria','pg') if b%2 else ('pg','maria')
        for i,arm in enumerate(arms):run(arm+('-diag' if mode=='diag' else ''),mode,b,i)
