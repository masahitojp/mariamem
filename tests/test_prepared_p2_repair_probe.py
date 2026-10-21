"""Negative controls for the new repair oracle; no guest behavior claim."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import v06_prepared_p2_repair_probe as probe


@pytest.mark.parametrize('fault', ['none','double-execution','stale-column-count'])
def test_schema_control_rejects_duplicate_execution_and_stale_metadata(monkeypatch,fault):
    calls=[];queries=[]
    monkeypatch.setattr(probe,'prepare',lambda *args:(7,None))
    monkeypatch.setattr(probe,'close_ping',lambda *args:None)
    def query(c,sql):
        queries.append(sql)
        if sql=='SELECT @p2_executions':
            return ((len(calls)+(1 if fault=='double-execution' else 0),),)
        return ()
    monkeypatch.setattr(probe.matrix,'query',query)
    def call(sid):
        assert sid==7;calls.append(sid)
        count=3 if len(calls)==2 and fault!='stale-column-count' else 2
        return dict(kind='rows',columns=[None]*count)
    if fault=='none':
        probe.schema_single_execution(object(),call)
        assert len(calls)==3
    else:
        with pytest.raises(AssertionError):
            probe.schema_single_execution(object(),call)
        assert len(calls)==2


def test_all_repair_scenarios_have_a_native_oracle():
    fixture=json.loads((Path(__file__).parent/'fixtures/prepared-p2-repair-native.json').read_text())
    assert len(fixture['cases'])==15
    assert set(probe.scenarios())==set(fixture['cases'])
    assert all(case['healthy_following_query'] and 'failure' not in case for case in fixture['cases'].values())


def test_selected_scenarios_preserve_original20(monkeypatch):
    names=list(probe.matrix.scenarios())
    monkeypatch.setattr(probe.matrix,'run_group',lambda info,case:dict(trace=[],healthy_following_query=True))
    result=probe.matrix.exercise(info={},selected={'single':object()})
    assert list(result['cases'])==['single']
    assert list(probe.matrix.scenarios())==names and len(names)==20
