"""Low-cost paired temporary-Snapshot comparison, using the existing harness."""
from pathlib import Path
import hashlib,json,os,platform,statistics,subprocess,sys,time

work=Path(__file__).resolve().parents[1]
repo,temp,evidence=work/'temp/source',work/'temp',work/'evidence'
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOMAXPROCS='2',TMPDIR=str(temp/'tmp'))
env.pop('MARIAMEM_TIMING_DIR',None)
source='3341f99000246fc64ae17b4ea39118f55589de1e'
binary=temp/'ownedprepared'
sys.path.insert(0,str(repo/'scripts'))
from git_identity import require_commit,verify_go_binary
require_commit(repo,source)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==source
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
buildinfo=verify_go_binary(repo,binary,source,go='go')
inputs=dict(source_commit=source,control_source_commit='2550bbe1ccf58f9cf65cf4cd801224907a7f9469',
    comparison='same clean prototype binary, MARIAMEM_SNAPSHOT_DIRECT=0 original path vs 1 direct path',
    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),binary_buildinfo=buildinfo,
    harness_sha256=hashlib.sha256((repo/'benchmarks/ownedprepared/main.go').read_bytes()).hexdigest(),
    campaign_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    platform=platform.platform(),gomaxprocs=2,trials_per_mode_per_cell=2,order=['original','direct','direct','original'],
    scope='local macOS feasibility; no release qualification; separate resources and traces',
    guest_sha256=json.loads((repo/'internal/generatedgo/provenance.json').read_text())['guest_sha256'],
    provenance_sha256=hashlib.sha256((repo/'internal/generatedgo/provenance.json').read_bytes()).hexdigest(),
    toolchain=subprocess.check_output(['go','version'],env=env,text=True).strip())
(evidence/'measurement-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
checks=json.loads((evidence/'verification.json').read_text())
assert all(r['returncode']==0 for r in checks if r['name']!='canonical-check')
assert all(r['returncode']==0 for r in json.loads((evidence/'builds.json').read_text()))
assert json.loads((evidence/'python-check.json').read_text())['returncode']==0
records=[]
def run(mode,payload,n,workers,index,kind='timing'):
    label=f'{kind}-p{payload}-n{n}-w{workers}-{index}-{mode}'
    out=evidence/(label+'.json')
    current=dict(env,MARIAMEM_SNAPSHOT_DIRECT='1' if mode=='direct' else '0')
    cmd=[str(binary),'-lifecycle','fork','-payload-mib',str(payload),'-forks',str(n),'-workers',str(workers),
         '-workload','crud','-tables','1','-label',source+':'+mode,'-out',str(out)]
    if kind=='resources': cmd+=['-go-resources']
    if kind=='trace':
        trace=temp/label; trace.mkdir()
        current['MARIAMEM_TIMING_DIR']=str(trace)
    begin=time.monotonic()
    with (evidence/(label+'.log')).open('w') as log:
        proc=subprocess.run(cmd,cwd=repo,env=current,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    record=dict(name=label,mode=mode,payload_mib=payload,forks=n,workers=workers,kind=kind,
                returncode=proc.returncode,process_wall_seconds=time.monotonic()-begin)
    records.append(record)
    (evidence/'campaign.json').write_text(json.dumps(records,indent=2)+'\n')
    if proc.returncode: raise RuntimeError(f'{label} failed; retain sample and stop')
    result=json.loads(out.read_text())
    ops=result['operations']
    def total(*prefixes): return sum(x['seconds'] for x in ops if any(x['name'].startswith(p) for p in prefixes))
    assert sum(x['name'].startswith('fork_ready_') for x in ops)==n
    assert sum(x['name'].startswith('mutation_') for x in ops)==n
    assert sum(x['name'].startswith('child_close_') for x in ops)==n
    record.update(snapshot_seconds=total('snapshot')-total('snapshot_close'),
        prepare_db_seconds=total('prepare_start','prepare_setup'),
        child_window_seconds=result['instance_suite_wall_seconds'],
        suite_product_seconds=result['suite_product_seconds'],
        suite_cpu_seconds=result['suite_cpu_seconds'],fds_before=result['fds_before'],fds_after=result['fds_after'])
    if kind=='trace':
        traces=[json.loads(x.read_text()) for x in sorted(trace.glob('*.json'))]
        (evidence/(label+'-traces.json')).write_text(json.dumps(traces,indent=2)+'\n')
    (evidence/'campaign.json').write_text(json.dumps(records,indent=2)+'\n')
    print(label,'snapshot',round(record['snapshot_seconds'],3),'suite',round(record['suite_product_seconds'],3),flush=True)

for payload,n,workers in [(p,n,1) for p in (0,10,100) for n in (4,16)]+[(10,16,4)]:
    for index,mode in enumerate(inputs['order']): run(mode,payload,n,workers,index)
for payload,n,workers in [(100,16,1),(10,16,4)]:
    for index,mode in enumerate(('original','direct')): run(mode,payload,n,workers,index,'resources')
for index,mode in enumerate(('original','direct')): run(mode,100,4,1,index,'trace')
summary=[]
for payload,n,workers in [(p,n,1) for p in (0,10,100) for n in (4,16)]+[(10,16,4)]:
    row=dict(payload_mib=payload,forks=n,workers=workers)
    for mode in ('original','direct'):
        group=[r for r in records if (r['payload_mib'],r['forks'],r['workers'],r['mode'],r['kind'])==(payload,n,workers,mode,'timing')]
        row[mode]={k:dict(median=statistics.median(r[k] for r in group),min=min(r[k] for r in group),max=max(r[k] for r in group))
                   for k in ('snapshot_seconds','prepare_db_seconds','child_window_seconds','suite_product_seconds','suite_cpu_seconds')}
    row['suite_saved_seconds']=row['original']['suite_product_seconds']['median']-row['direct']['suite_product_seconds']['median']
    row['suite_saved_pct']=row['suite_saved_seconds']/row['original']['suite_product_seconds']['median']*100
    summary.append(row)
(evidence/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
