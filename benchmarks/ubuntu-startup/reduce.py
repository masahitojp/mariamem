#!/usr/bin/env python3
"""Offline exact-inventory and operation-timeline oracle; no guest execution."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from campaign import case_plan

PREFIXES=('fork_ready','point_use','count_use','mutation','disconnect','child_close')

def checked_metrics(case,data):
    if (data['payload_mib'],data['tables'],data['forks'],data['workers'],data['phase_mode'],data['diagnostic'],data['requested_procs'])!=(10,8,4,case['workers'],case['mode'],case['diagnostic'],case['procs']):raise ValueError('wrong case dimensions')
    expected={'prepare_start','prepare_setup','snapshot','snapshot_close'}|{f'{p}_{i:02d}' for p in PREFIXES for i in range(4)}
    ops={op['name']:op for op in data['operations']}
    if len(ops)!=len(data['operations']) or set(ops)!=expected:raise ValueError('missing/duplicate operation')
    for op in ops.values():
        if not (0<=op['begin_ns']<=op['end_ns']) or op['seconds']<0:raise ValueError('invalid timeline')
    latest=max(ops[f'fork_ready_{i:02d}']['end_ns'] for i in range(4))
    for i in range(4):
        keys=[f'{p}_{i:02d}' for p in PREFIXES]
        if any(ops[a]['end_ns']>ops[b]['begin_ns'] for a,b in zip(keys,keys[1:])):raise ValueError('invalid child order')
    if data['all_ready_callback_ns']<latest:raise ValueError('premature all-ready callback')
    if case['mode']=='barrier' and any(ops[f'point_use_{i:02d}']['begin_ns']<data['all_ready_callback_ns'] for i in range(4)):raise ValueError('SQL before barrier')
    if case['procs'] and data['gomaxprocs']!=case['procs']:raise ValueError('GOMAXPROCS override lost')
    if data['startup_wall_seconds']<=0 or data['startup_cpu_seconds']<0 or data['startup_gc_cpu_seconds']<0:raise ValueError('invalid counters')
    return {
        'fork_ms':[ops[f'fork_ready_{i:02d}']['seconds']*1000 for i in range(4)],
        'serial_fork_cpu_ms':[ops[f'fork_ready_{i:02d}']['cpu_seconds']*1000 for i in range(4)] if case['workers']==1 else [],
        'children_wall_ms':data['instance_suite_wall_seconds']*1000,
        'all_ready_wall_ms':data['startup_wall_seconds']*1000,
        'startup_cpu_ms':data['startup_cpu_seconds']*1000,
        'startup_cpu_per_wall':data['startup_cpu_seconds']/data['startup_wall_seconds'],
        'startup_gc_cpu_ms':data['startup_gc_cpu_seconds']*1000,
        'startup_gc_cycles':data['startup_gc_cycles'],
        'callback_lag_ms':(data['all_ready_callback_ns']-latest)/1e6,
        'gomaxprocs':data['gomaxprocs'],
        'phases_started_before_last_ready':{p:sum(ops[f'{p}_{i:02d}']['begin_ns']<latest for i in range(4)) for p in PREFIXES[1:]},
    }

def stats(values):return dict(n=len(values),median=statistics.median(values),min=min(values),max=max(values))

def reduce(root):
    receipt=json.loads((root/'receipt.json').read_text())
    if not receipt['completed']:raise ValueError('incomplete campaign')
    expected={c['name']:c for c in case_plan()}
    if len(receipt['cases'])!=32 or {c['name'] for c in receipt['cases']}!=set(expected):raise ValueError('wrong case inventory')
    commit=receipt['source_identity']['source_commit'];stamp=receipt['build_info']
    if receipt['source_identity']['object_type']!='commit' or 'vcs.revision='+commit not in stamp or 'vcs.modified=false' not in stamp or 'CGO_ENABLED=0' not in stamp or not stamp.splitlines()[0].endswith(' go1.26.8'):raise ValueError('wrong binary identity')
    cells={};groups={}
    for case in receipt['cases']:
        plan=expected[case['name']]
        if any(case[k]!=plan[k] for k in plan) or case['exit_code']!=0:raise ValueError('case differs from plan')
        file=root/(case['name']+'.json')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=case['output_sha256']:raise ValueError('changed output')
        data=json.loads(file.read_text());metrics=checked_metrics(case,data);cells[case['name']]=metrics
        key=f"{case['cohort']}/{case['mode']}/w{case['workers']}/p{case['procs']}"
        group=groups.setdefault(key,{})
        for name,value in metrics.items():
            if isinstance(value,dict):continue
            group.setdefault(name,[]).extend(value if isinstance(value,list) else [value])
    return dict(result='PASS',source_commit=commit,cells=cells,groups={k:{name:stats(v) for name,v in g.items() if v} for k,g in groups.items()})

def main():
    p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args()
    result=reduce(a.evidence);(a.evidence/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: exact 32 cases, dimensions, identities, hashes and child/barrier timelines')

if __name__=='__main__':main()
