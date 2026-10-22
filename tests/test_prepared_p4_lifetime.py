"""Pin the first P4 native boundary and reject comparison omissions."""
import copy
import json
from pathlib import Path

from v06_prepared_p4_lifetime import CASES, comparable

ROOT=Path(__file__).resolve().parents[1]


def test_native_lifetime_inventory_and_boundaries():
    r=json.loads((ROOT/'tests/fixtures/prepared-p4-lifetime-native.json').read_text())
    assert r['result']=='PASS' and not r['failures']
    assert set(r['cases'])=={*CASES,'go-DB-Tx-Conn-pool'}
    for name,case in r['cases'].items():
        assert case['result']=='PASS',name
    short=r['cases']['malformed-lifecycle-adjacency']['trace']
    assert [c['length'] for c in short]==list(range(6))
    assert short[0]['after_kind']=='ok'
    assert all(c['after_kind']=='unknown-handle' for c in short[1:])
    assert r['cases']['native-quota-and-recovery']['trace'][0]['quota_errno']==1461
    for mode in ('quit','eof'):
        case=r['cases'][f'idle-{mode}-cleanup']
        assert case['trace']==[dict(sessions=12,statements_per_session=4,live_after=0,rollback=True)]
    c=r['cases']['go-DB-Tx-Conn-pool']['consumer']
    assert len(c['checks'])==6 and c['prepared_before']==c['prepared_after']==c['open_after']==0


def test_comparison_preserves_native_packets_counters_and_consumer_failures():
    r=json.loads((ROOT/'tests/fixtures/prepared-p4-lifetime-native.json').read_text())
    for name,case in r['cases'].items():
        original=comparable(case)
        if 'trace' in case:
            changed=copy.deepcopy(case);changed['trace'].append({'unexpected':'packet'})
        else:
            changed=copy.deepcopy(case);changed['consumer']['open_after']=1
        assert comparable(changed)!=original,name
        assert 'runtime' not in original and 'logs' not in original
