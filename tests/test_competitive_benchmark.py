import copy
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('competitive',Path(__file__).resolve().parents[1]/'benchmarks/testcontainers_compare.py')
bench=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

def evidence():
    samples=[]
    for scenario in ('empty','fixture'):
        for n in (1,4,8):
            for backend in ('mariamem','testcontainers'):
                for round in range(2):
                    samples.append({'scenario':scenario,'workers':n,'backend':backend,'phase':'measurement','round':round,
                                    'group_ready_seconds':2+round,'runner_cpu_seconds':.1,
                                    'per_db':[{'latency_seconds':1+round,'startup_seconds':.5,'fixture_seconds':.4 if scenario=='fixture' else 0,
                                               'ready_cost':{'cpu_seconds':.2,'rss_bytes':123} if backend=='mariamem' else {'error':'unavailable'},
                                               'server_version':backend+'-version'} for _ in range(n)]})
    samples.append({'phase':'warmup'})
    return {'runs':2,'samples':samples}

def test_summary_keeps_group_and_individual_readiness_separate():
    result=bench.summary(evidence())
    assert len(result)==12
    assert result[0]['latency_seconds']=={'p50':1.5,'p95':1.95}
    assert result[0]['group_ready_seconds']=={'p50':2.5,'p95':2.95}
    assert result[0]['ready_cpu_seconds']['samples']==2
    assert result[1]['ready_cpu_seconds']=={'samples':0}
    assert result[-1]['instances']==16
    assert result[0]['fixture_seconds']['p50']==0
    assert result[-1]['fixture_seconds']['p50']==.4

def test_summary_rejects_missing_batch_and_instance():
    r=evidence();r['samples'].pop(0)
    with pytest.raises(ValueError,match='batch'):bench.summary(r)
    r=evidence();r['samples'][0]['per_db']=[]
    with pytest.raises(ValueError,match='instance'):bench.summary(r)

def test_warmup_never_enters_percentiles():
    r=evidence();r['samples'][-1]={'phase':'warmup','scenario':'empty','workers':1,'backend':'mariamem','per_db':[{'latency_seconds':999}]}
    assert bench.summary(r)==bench.summary(evidence())


def test_duplicate_round_cannot_stand_in_for_missing_round():
    r=evidence();r['samples'][1]['round']=0
    with pytest.raises(ValueError,match='batch'):bench.summary(r)
