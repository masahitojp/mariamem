#!/usr/bin/env python3
"""Candidate measurement with the unchanged v0.4 public-API fixture/harness.

Separate from release acceptance; does not enable or publish a runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from _common import ROOT, environment
from final_latency import distribution
from isolation_baseline import percentile
from memory_envelope import summarize

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-dir',type=Path,help='explicit legacy bundle; omitted selects production direct-link')
    p.add_argument('--json',type=Path,required=True)
    p.add_argument('--runs',type=int,default=30)
    p.add_argument('--scaling-runs',type=int,default=3)
    p.add_argument('--fresh-resources-only',action='store_true',help='separate Start CPU/ready physical-memory probe; does not mix with latency trials')
    a=p.parse_args()
    if a.runs<30 or a.scaling_runs<1:p.error('30+ startup trials and positive scaling trials required')
    native=a.native_dir.resolve() if a.native_dir else None;out=a.json.resolve();out.parent.mkdir(parents=True,exist_ok=True)
    binary=ROOT/'build/bench/isolation-go';helper=ROOT/'build/bench/process-cost';binary.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['go','build','-trimpath','-o',str(binary),'./benchmarks/goisolation'],cwd=ROOT,check=True)
    subprocess.run(['cc','-O2',str(ROOT/'benchmarks/tools/process_cost.c'),'-o',str(helper)],check=True)
    manifest=json.loads((native/'manifest.json').read_text()) if native else None
    for name,digest in (manifest or {}).get('sha256',{}).items():
        if hashlib.sha256((native/name).read_bytes()).hexdigest()!=digest:raise ValueError('native checksum mismatch: '+name)
    report=dict(schema_version=1,completed=False,boundary='public Go Start/Fork; exact bundle verification + compiled-guest binding + MySQL wire + first SQL; prepared COUNT uses 1000 rows',environment=environment(SimpleNamespace(backend='none')),native_manifest=manifest,runs=a.runs,scaling_runs=a.scaling_runs,trials=[])
    report['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    report['runtime_kind']='wasmer' if native else 'direct-linked generated-Go'
    if not native:report['boundary']='public Go Start/Fork; compiled guest identity + snapshot verification + MySQL wire + first SQL; 1000-row fixture; same process hosts all instances'
    report['harness_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),*sorted((ROOT/'benchmarks/goisolation').glob('*.go'))]}
    env=os.environ.copy()
    for k in ['MARIAMEM_TIMING_DIR','MARIAMEM_INIT_DIAGNOSTICS','MARIAMEM_MEMORY_DIAGNOSTICS','MARIAMEM_COST_HELPER','MARIAMEM_NATIVE_DIR','MARIAMEM_RUNTIME']:env.pop(k,None)
    def save():out.write_text(json.dumps(report,indent=2)+'\n')
    def trial(kind,n,phase,i):
        raw=out.with_name(f'{out.stem}-{kind}-{n}-{phase}-{i}.json')
        cmd=[str(binary),'--native-dir',str(native) if native else '', '--json',str(raw),'--runs','1','--warmup','0','--workers',str(n),'--rows','1000','--queries','10']
        e=env.copy()
        if kind in ['batch','fresh']:cmd+=['--resource-probe','fresh' if kind=='fresh' else 'batch'];e['MARIAMEM_COST_HELPER']=str(helper)
        with raw.with_suffix('.log').open('w') as log:r=subprocess.run(cmd,cwd=ROOT,env=e,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        data=json.loads(raw.read_text()) if raw.exists() else None
        row=dict(kind=kind,workers=n,phase=phase,round=i,exit_code=r.returncode,status='pass' if r.returncode==0 and data and data['completed'] else 'failed',report=data)
        report['trials'].append(row);save();print(kind,n,phase,i,row['status'],flush=True)
        if row['status']!='pass':raise RuntimeError('failed candidate trial: '+str(raw))
    try:
        if a.fresh_resources_only:
            report['boundary']='public Go Start + first SELECT 1; counters just after all-ready, includes observer/version query cost, excludes teardown'
            for i in range(a.runs):trial('fresh',1,'measurement',i)
            rows=[t['report']['samples'][0] for t in report['trials']]
            report['fresh_resources']={key:distribution([r[key] for r in rows]) for key in ['group_ready_seconds','combined_cpu_seconds','host_cpu_seconds','runtime_cpu_seconds','average_incremental_bytes','incremental_primary_bytes']}
            for state in ['ready','baseline','after_close']:
                for key in ['primary_bytes','rss_bytes']:
                    report['fresh_resources'][state+'_'+key]=distribution([r[state][key] for r in rows])
            report['completed']=True
            return
        for phase,count in [('warmup',2),('measurement',a.runs)]:
            for i in range(count):trial('startup',1,phase,i)
        for i in range(a.scaling_runs):
            for n in [1,4,8,16]:trial('batch',n,'measurement',i)
        samples=[s for t in report['trials'] if t['kind']=='startup' and t['phase']=='measurement' for s in t['report']['samples']]
        report['startup']={}
        for case in ['start_first_sql','start_seeded','snapshot','fork_first_sql']:
            vals=[s['latency_seconds'] for s in samples if s['case']==case]
            report['startup'][case]=dict(distribution(vals),p99=percentile(vals,.99),ge500ms=sum(x>=.5 for x in vals),ge900ms=sum(x>=.9 for x in vals))
        report['scaling']=summarize(report['trials']);report['completed']=True
    finally:save()

if __name__=='__main__':main()
