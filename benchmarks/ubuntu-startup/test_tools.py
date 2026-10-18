import copy
import pytest
from campaign import case_plan
from reduce import checked_metrics,PREFIXES


def fixture():
    case=next(c for c in case_plan() if c['cohort']=='ordinary' and c['mode']=='barrier')
    ops=[]
    for name in ['prepare_start','prepare_setup','snapshot','snapshot_close']:
        ops.append(dict(name=name,begin_ns=0,end_ns=1,seconds=1e-9,cpu_seconds=0))
    for i in range(4):
        for j,prefix in enumerate(PREFIXES):
            begin=10 if j==0 else 30+j*10
            ops.append(dict(name=f'{prefix}_{i:02d}',begin_ns=begin,end_ns=begin+1,seconds=1e-9,cpu_seconds=None))
    data=dict(payload_mib=10,tables=8,forks=4,workers=4,phase_mode='barrier',diagnostic='none',requested_procs=0,gomaxprocs=2,all_ready_callback_ns=20,startup_wall_seconds=.1,startup_cpu_seconds=.2,startup_gc_cpu_seconds=0,startup_gc_cycles=0,instance_suite_wall_seconds=.2,operations=ops)
    return case,data


def test_fixed_cohorts():
    plan=case_plan()
    assert len(plan)==32 and len({c['name'] for c in plan})==32
    assert {k:sum(c['cohort']==k for c in plan) for k in ['ordinary','procs','cpu','trace']}==dict(ordinary=15,procs=9,cpu=6,trace=2)


def test_valid_barrier():
    case,data=fixture();r=checked_metrics(case,data)
    assert all(v==0 for v in r['phases_started_before_last_ready'].values())


@pytest.mark.parametrize('defect',['missing','duplicate','early-sql','premature-ready','wrong-procs','wrong-size'])
def test_bad_evidence_rejected(defect):
    case,data=fixture();case=copy.deepcopy(case)
    if defect=='missing':data['operations'].pop()
    elif defect=='duplicate':data['operations'].append(data['operations'][0])
    elif defect=='early-sql':next(v for v in data['operations'] if v['name']=='point_use_00')['begin_ns']=15
    elif defect=='premature-ready':data['all_ready_callback_ns']=0
    elif defect=='wrong-procs':case['procs']=4;data['requested_procs']=4
    elif defect=='wrong-size':data['payload_mib']=0
    with pytest.raises(ValueError):checked_metrics(case,data)


def complete_receipt(tmp_path):
    import hashlib,json
    _,template=fixture()
    cases=[]
    for plan in case_plan():
        data=copy.deepcopy(template)
        data.update(workers=plan['workers'],phase_mode=plan['mode'],diagnostic=plan['diagnostic'],requested_procs=plan['procs'],gomaxprocs=plan['procs'] or 2)
        if plan['workers']==1:
            for op in data['operations']:op['cpu_seconds']=0
        raw=json.dumps(data).encode();(tmp_path/(plan['name']+'.json')).write_bytes(raw)
        cases.append(dict(**plan,exit_code=0,output_sha256=hashlib.sha256(raw).hexdigest()))
    sha='a'*40
    receipt=dict(completed=True,source_identity=dict(source_commit=sha,object_type='commit'),build_info=f'binary: go1.26.8\n vcs.revision={sha}\n vcs.modified=false\n CGO_ENABLED=0\n',cases=cases)
    (tmp_path/'receipt.json').write_text(json.dumps(receipt))
    return receipt


def test_complete_input_reconciles(tmp_path):
    from reduce import reduce
    complete_receipt(tmp_path)
    assert len(reduce(tmp_path)['cells'])==32


@pytest.mark.parametrize('defect',['incomplete','missing-case','wrong-stamp','changed-output'])
def test_campaign_evidence_rejected(tmp_path,defect):
    import json
    from reduce import reduce
    receipt=complete_receipt(tmp_path)
    if defect=='incomplete':receipt['completed']=False
    elif defect=='missing-case':receipt['cases'].pop()
    elif defect=='wrong-stamp':receipt['build_info']=receipt['build_info'].replace('vcs.modified=false','vcs.modified=true')
    else:(tmp_path/(receipt['cases'][0]['name']+'.json')).write_text('{}')
    (tmp_path/'receipt.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError):reduce(tmp_path)
