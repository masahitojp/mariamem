import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
import memory_envelope as envelope


def sample(n, round=0):
    row = {'group_ready_seconds': .5, 'host_cpu_seconds': .1, 'runtime_cpu_seconds': .2,
           'combined_cpu_seconds': .3, 'incremental_primary_bytes': n*100,
           'average_incremental_bytes': 100, 'group_peak_primary_bytes': 50+n*100,
           'incremental_peak_primary_bytes': n*100}
    for state, value in [('baseline',50),('ready',50+n*100),('after_close',55)]:
        row[state]={'primary_bytes':value,'rss_bytes':value+10,'private_bytes':None}
    return {'kind':'batch','workers':n,'round':round,'phase':'measurement','status':'pass','report':{'samples':[row]}}


def test_scaling_summary_preserves_incremental_and_partial_failures():
    trials=[sample(n) for n in (1,4,8)]
    trials.append({'kind':'batch','workers':16,'round':0,'phase':'measurement','status':'failed','report':None})
    summary=envelope.summarize(trials)
    assert summary['groups'][0]['after_close_minus_baseline_bytes']['p50']==5
    assert summary['groups'][0]['ready_private_bytes'] is None
    assert summary['groups'][3]['successes']==0
    assert summary['groups'][3]['failures']==1
    assert summary['groups'][3]['group_ready_seconds'] is None
    assert summary['marginal_memory'][0]['bytes_per_added_db']['p50']==100
    assert summary['marginal_memory'][2]['bytes_per_added_db'] is None


def test_supervisor_retains_crash_without_report(tmp_path):
    child=tmp_path/'child'
    child.write_text('#!/bin/sh\nexit 137\n');child.chmod(0o700)
    result=envelope.run_trial(child,tmp_path,child,tmp_path/'result.json','batch',16,'measurement',0,5)
    assert result['status']=='failed' and result['exit_code']==137
    assert result['report'] is None and '137' in result['error']
    assert 'OOM' not in result['error']


def test_supervisor_success_reads_exact_child_report(tmp_path):
    child=tmp_path/'child.py'
    child.write_text('#!/usr/bin/env python3\nimport sys,json,pathlib\np=pathlib.Path(sys.argv[sys.argv.index("--json")+1]);p.write_text(json.dumps({"completed":True,"samples":[]}))\n')
    child.chmod(0o700)
    result=envelope.run_trial(child,tmp_path,child,tmp_path/'result.json','sessions',1,'measurement',0,5)
    assert result['status']=='pass' and result['report']['completed']
