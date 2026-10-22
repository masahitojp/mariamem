"""Pin active-query witnesses and distinguish native/product failure contracts."""
import copy
import json
from pathlib import Path
import pytest

from v06_prepared_active_probe import COMMON,PRODUCT_ONLY,validate_reference

ROOT=Path(__file__).resolve().parents[1]

def native():return json.loads((ROOT/'tests/fixtures/prepared-active-native.json').read_text())


def product_control():
    n=native();r=copy.deepcopy(n)
    for name in PRODUCT_ONLY:r['cases'][name]=copy.deepcopy(n['cases']['active-eof'])
    for name,c in r['cases'].items():
        if name!='ordinary-error':c['fatal_DB']={'code':'unusable','closed':True,'new_SQL_admission_rejected':True}
        for key in ('target_log_removed','shared_lineage_retained_while_baseline_alive','sibling_usable_and_unchanged','baseline_reusable_with_prepared_QUERY','lineage_temporary_removed'):c[key]=True
    r['cases']['active-db-close']['explicit_Close_new_SQL_rejected']=True
    return r


def test_native_inventory_execution_witness_and_resource_boundaries():
    n=native();assert n['result']=='PASS' and not n['failures'];assert set(n['cases'])==set(COMMON) and len(COMMON)==5 and len(PRODUCT_ONLY)==2
    for name,c in n['cases'].items():
        assert c['native_cleanup']['prepared_after']==0 and c['native_cleanup']['baseline_value']==7
        assert c['native_cleanup']['transaction_rollback_checked']==(name!='ordinary-error')
        if name!='ordinary-error':
            w=c['witness'];assert w['actor_id']==w['lock_owner']>0 and w['uncommitted_write_hidden']
    assert n['cases']['go-cancel']['consumer']['execute_error']=='context canceled'
    assert n['cases']['go-deadline']['consumer']['execute_error']=='context deadline exceeded'
    assert n['cases']['active-reset']['consumer']['transport_failed']
    e=n['cases']['ordinary-error']['error_packets'][0];assert e['errno']==1644 and e['sqlstate']=='45000'
    assert validate_reference(product_control(),n)['shared_observable_outcomes']=='PASS'


@pytest.mark.parametrize('defect',['witness','rollback','resource-count','context-error','pool-leak','metadata','fatal-state','admission','sibling','baseline','lineage'])
def test_reference_gate_rejects_missing_evidence_or_wrong_disposition(defect):
    n=native();r=product_control();c=r['cases']['go-cancel']
    if defect=='witness':c['witness']['lock_owner']+=1
    elif defect=='rollback':n['cases']['go-cancel']['native_cleanup']['transaction_rollback_checked']=False
    elif defect=='resource-count':n['cases']['go-cancel']['native_cleanup']['prepared_after']=1
    elif defect=='context-error':c['consumer']['execute_error']='unexpected success'
    elif defect=='pool-leak':c['consumer']['open_after']=1
    elif defect=='metadata':r['cases']['ordinary-error']['error_packets'][0]['error_packet']='00'
    elif defect=='fatal-state':c['fatal_DB']['closed']=False
    elif defect=='admission':c['fatal_DB']['new_SQL_admission_rejected']=False
    elif defect=='sibling':c['sibling_usable_and_unchanged']=False
    elif defect=='baseline':c['baseline_reusable_with_prepared_QUERY']=False
    elif defect=='lineage':c['lineage_temporary_removed']=False
    with pytest.raises(AssertionError):validate_reference(r,n)
