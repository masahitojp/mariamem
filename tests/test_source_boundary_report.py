"""Source condition, staging and byte identity evidence must be complete."""
import copy
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'benchmarks'))
from source_boundary_report import summarize


def probe(prefix):
    stage = dict(wall_ns=10,process_cpu_ns=8,thread_cpu_ns=7,bytes=5,calls=1,invalid_clock=False)
    return dict(version=1,invalid_clock=False,dropped_files=0,file_count=1,directories=1,
                wall_ns=100,process_cpu_ns=80,thread_cpu_ns=70,
                stages={'read': stage.copy(),'write': stage.copy()},
                files=[dict(path=prefix+'a',size_bytes=5,wall_ns=80,stages={'read':stage.copy(),'write':stage.copy()})])


def report(source):
    g={'restore_copy':probe('/restore-source/' if source=='guest' else '/snapshot-in/data/'),
       'restore_source':source,'restore_identity_verified':True,
       'restore_verification':dict(wall_ns=200,process_cpu_ns=150,thread_cpu_ns=120,invalid_clock=False)}
    if source=='guest': g['restore_prestage']=probe('/snapshot-in/data/')
    return {'samples':[dict(case='fork_first_sql',phase='measurement',workers=1,
                           per_db=[dict(stage_timings={'host':{'guest':g}})])]}


def test_source_evidence_and_separate_costs():
    pairs=[{'control':report('host'),'reuse':report('guest')}]
    result=summarize(pairs)
    assert any(r['component']=='pre-stage' and r['metric']=='bytes' and r['p50']==5 for r in result['reuse'])
    assert any(r['component']=='verification' and r['p50']==200 for r in result['control'])
    bad=copy.deepcopy(pairs)
    bad[0]['reuse']['samples'][0]['per_db'][0]['stage_timings']['host']['guest']['restore_identity_verified']=False
    with pytest.raises(ValueError,match='content verification'):summarize(bad)
    bad=copy.deepcopy(pairs)
    bad[0]['reuse']['samples'][0]['per_db'][0]['stage_timings']['host']['guest']['restore_prestage']['files'][0]['path']='/snapshot-in/data/wrong'
    with pytest.raises(ValueError,match='inventory mismatch'):summarize(bad)
