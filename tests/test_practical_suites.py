import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('practical',Path(__file__).resolve().parents[1]/'benchmarks/practical_suites.py')
bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)

def evidence():
    suites=[]
    for mode in bench.MODES:
        for i in range(3):
            raw={'completed':True,'server_version':'version','suite_wall_seconds':i+1,'setup_wall_seconds':.2,
                 'runner_cpu_seconds':.3,'waited_children_cpu_seconds':.4,
                 'samples':[{'fixture_ready_seconds':.2,'cleanup_seconds':.01} for _ in range(10)]}
            suites.append({'phase':'measurement','mode':mode,'tests':10,'round':i,'report':raw})
    return {'completed':True,'counts':[10],'runs':3,'suites':suites}

def test_suite_summary_distinguishes_shared_and_fresh_server():
    rows=bench.summarize(evidence())
    assert [r['mode'] for r in rows]==list(bench.MODES)
    assert rows[0]['suite_wall_seconds']['p50']==2
    assert rows[0]['fixture_ready_seconds']['count']==30

def test_failure_missing_tests_and_changed_versions_fail_closed():
    r=evidence();r['completed']=False
    with pytest.raises(ValueError,match='incomplete'):bench.summarize(r)
    r=evidence();r['suites'][0]['report']['samples'].pop()
    with pytest.raises(ValueError,match='missing'):bench.summarize(r)
    r=evidence();r['suites'][0]['report']['server_version']='other'
    with pytest.raises(ValueError,match='version'):bench.summarize(r)
