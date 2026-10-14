"""Authorized finite follow-up: 100 MiB, 16 serial Forks, eight runs only."""
from pathlib import Path
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time

work = Path(__file__).resolve().parents[1]
repo, temp, evidence = work/'temp/source', work/'temp', work/'evidence'
source = '3341f99000246fc64ae17b4ea39118f55589de1e'
env = dict(os.environ, GOTOOLCHAIN='go1.26.8', GOMAXPROCS='2',
           GOCACHE=str(temp/'gocache'), TMPDIR=str(temp/'tmp'), GOTMPDIR=str(temp/'go-tmp'))
env.pop('MARIAMEM_TIMING_DIR', None)
sys.path.insert(0, str(repo/'scripts'))
from git_identity import require_commit, verify_go_binary

require_commit(repo, source)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip() == source
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
binary = temp/'ownedprepared'
command = ['go','build','-p','1','-buildvcs=true','-o',str(binary),'./benchmarks/ownedprepared']
start = time.monotonic()
print('building exact source', source, flush=True)
with (evidence/'build.txt').open('w') as log:
    result = subprocess.run(command,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1500)
(evidence/'build.json').write_text(json.dumps(dict(source_commit=source,command=command,
    returncode=result.returncode,seconds=time.monotonic()-start),indent=2)+'\n')
if result.returncode:
    raise RuntimeError('build failed; stop without measurement')
buildinfo = verify_go_binary(repo,binary,source,go='go')
inputs = dict(source_commit=source,baseline_source_commit='2550bbe1ccf58f9cf65cf4cd801224907a7f9469',
    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),binary_buildinfo=buildinfo,
    harness_sha256=hashlib.sha256((repo/'benchmarks/ownedprepared/main.go').read_bytes()).hexdigest(),
    runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    provenance_sha256=hashlib.sha256((repo/'internal/generatedgo/provenance.json').read_bytes()).hexdigest(),
    guest_sha256=json.loads((repo/'internal/generatedgo/provenance.json').read_text())['guest_sha256'],
    platform=platform.platform(),toolchain=subprocess.check_output(['go','version'],env=env,text=True).strip(),
    gomaxprocs=2,order=['original','direct','direct','original'],trials_per_mode_per_observation=2,
    scope='100 MiB; 16 serial Forks; ordinary then resource-observed ABBA; eight runs; no implementation changes',
    env_overrides={k:env[k] for k in ('GOTOOLCHAIN','GOMAXPROCS','GOCACHE','TMPDIR','GOTMPDIR')},
    inherited_go_env={k:os.environ.get(k) for k in ('GOGC','GOMEMLIMIT','GODEBUG','GOFLAGS')})
(evidence/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
print('build identity verified; beginning eight runs',flush=True)
records = []
campaign_start = time.monotonic()
for kind in ('timing','resources'):
    for index,mode in enumerate(inputs['order']):
        if time.monotonic()-campaign_start > 900:
            raise RuntimeError('bounded campaign time exceeded; stop')
        label = f'{kind}-{index}-{mode}'
        cmd = [str(binary),'-lifecycle','fork','-payload-mib','100','-forks','16','-workers','1',
               '-workload','crud','-tables','1','-label',source+':'+mode,'-out',str(evidence/(label+'.json'))]
        if kind == 'resources': cmd += ['-go-resources']
        current = dict(env,MARIAMEM_SNAPSHOT_DIRECT='1' if mode=='direct' else '0')
        begin = time.monotonic()
        with (evidence/(label+'.txt')).open('w') as log:
            result = subprocess.run(cmd,cwd=repo,env=current,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        row = dict(name=label,mode=mode,kind=kind,command=cmd,returncode=result.returncode,
                   process_wall_seconds=time.monotonic()-begin)
        records.append(row)
        (evidence/'campaign.json').write_text(json.dumps(records,indent=2)+'\n')
        if result.returncode: raise RuntimeError('scenario failed; retain failure and stop')
        data = json.loads((evidence/(label+'.json')).read_text())
        operations = data['operations']
        for prefix in ('fork_ready_','mutation_','child_close_'):
            assert sum(o['name'].startswith(prefix) for o in operations) == 16
        def total(*names): return sum(o['seconds'] for o in operations if o['name'] in names)
        row.update(snapshot_seconds=total('snapshot'),prepare_db_seconds=total('prepare_start','prepare_setup'),
                   child_window_seconds=data['instance_suite_wall_seconds'],suite_product_seconds=data['suite_product_seconds'],
                   suite_cpu_seconds=data['suite_cpu_seconds'],fds_before=data['fds_before'],fds_after=data['fds_after'])
        if kind == 'resources':
            observation = data['go_resource_observation']
            row.update(cumulative_alloc_bytes=observation['cumulative_alloc_bytes'],
                       process_peak_rss_bytes=observation['process_peak_rss_bytes'],
                       gc_cycles=observation['after']['num_gc']-observation['before']['num_gc'],
                       mappings_after=observation['after']['linear_memory_virtual'])
        (evidence/'campaign.json').write_text(json.dumps(records,indent=2)+'\n')
        print(label,'Snapshot',round(row['snapshot_seconds'],3),'children',round(row['child_window_seconds'],3),
              'suite',round(row['suite_product_seconds'],3),'GC',row.get('gc_cycles'),flush=True)
summary = []
for kind in ('timing','resources'):
    row = dict(kind=kind)
    keys = ['snapshot_seconds','prepare_db_seconds','child_window_seconds','suite_product_seconds','suite_cpu_seconds']
    if kind=='resources': keys += ['cumulative_alloc_bytes','process_peak_rss_bytes','gc_cycles']
    for mode in ('original','direct'):
        group = [r for r in records if (r['kind'],r['mode']) == (kind,mode)]
        row[mode] = {k:dict(median=statistics.median(r[k] for r in group),min=min(r[k] for r in group),
                           max=max(r[k] for r in group)) for k in keys}
    a,b = (row[m]['suite_product_seconds']['median'] for m in ('original','direct'))
    row['suite_saved_seconds'],row['suite_saved_pct'] = a-b,(a-b)/a*100
    summary.append(row)
(evidence/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print('eight runs complete',flush=True)
