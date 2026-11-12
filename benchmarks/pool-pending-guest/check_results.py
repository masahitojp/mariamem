#!/usr/bin/env python3
"""Read-only replay and focused corrupt-evidence controls."""
import copy, hashlib, json, pathlib

def validate(rows):
    arms={'pending_unreported','pending_reported','late_submit'}
    expected={(a,c,r) for a in arms for c in (1,16) for r in (1,2,3)}
    assert len(rows)==18
    assert {(r['Arm'],r['Concurrency'],r['Repeat']) for r in rows}==expected
    for r in rows:
        assert r['Result']=='PASS'
        assert r['MappingsBefore']==r['MappingsAfter']
        assert r['Created']==r['Retired']==2 and r['RefBalance']==0
        es=r['Events']; names=[e['Name'] for e in es]
        assert len({e['Pool'] for e in es})==1 and es[0]['Pool']>0
        assert all(a['MS']<=b['MS'] for a,b in zip(es,es[1:]))
        assert names.count('timer_suppressed')==1 and names.count('pending_clear')==2
        assert names.count('a_start')==names.count('a_end')==names.count('b_run')==1
        assert names.count('worker_init')==names.count('worker_retire')==2
        assert names.count('pool_disposed')==1
        first=lambda x:names.index(x)
        assert first('submit_a')<first('worker_init')<first('pending_clear')<first('a_start')
        assert first('submit_b')<first('b_run')<first('pool_disposed')
        assert first('a_end')<first('pool_disposed')
        if r['Arm']=='late_submit':
            assert 'pending_refusal' not in names and 'maintenance' not in names
            assert first('a_start')<first('submit_b')
        else:
            assert names.count('pending_refusal')==1
            assert first('submit_b')<first('pending_refusal')<first('pending_clear')
        if r['Arm']=='pending_unreported':
            assert 50<=r['ObservationMS']<250
            assert (r['Occupied'],r['Waiting'],r['Long'],r['Pending'],r['Queued'])==(1,0,0,0,1)
            assert first('a_start')<first('futex_wait')<first('maintenance')<first('b_run')
            assert 'wait_begin' not in names
        elif r['Arm']=='pending_reported':
            assert 'maintenance' not in names
            assert first('wait_begin')<first('b_run')<first('wait_end')

def main():
    here=pathlib.Path(__file__).resolve().parent
    sums=json.loads((here/'SHA256SUMS.json').read_text())
    for name,digest in sums.items():
        assert hashlib.sha256((here/name).read_bytes()).hexdigest()==digest,name
    rows=json.loads((here/'results/cases.json').read_text()); validate(rows)
    controls=[lambda r:r.pop(),lambda r:r[0].update(Result='FAIL'),lambda r:r[0].update(Queued=0),lambda r:r[0].update(MappingsAfter=999),lambda r:r[0]['Events'].__setitem__(0,dict(r[0]['Events'][0],Pool=999)),lambda r:r[0]['Events'].reverse()]
    for mutate in controls:
        bad=copy.deepcopy(rows);mutate(bad)
        try:validate(bad)
        except AssertionError:pass
        else:raise AssertionError('corrupt evidence accepted')
    print('18 cases replay PASS; 6 corrupt-evidence controls rejected')
if __name__=='__main__':main()
