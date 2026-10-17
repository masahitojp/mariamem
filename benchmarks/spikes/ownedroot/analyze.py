#!/usr/bin/env python3
"""Check saved results; report per-route claims and explicit observation limits."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def main():
    out=HERE/'evidence'
    for item in json.loads((out/'files.json').read_text()):
        assert hashlib.sha256((out/item['file']).read_bytes()).hexdigest()==item['stored_sha256']
    r=json.loads((out/'receipt.json').read_text())
    assert r['result']=='PASS'
    for run in r['runs']:
        assert run['exit_code']==0 and run['tests']
        assert all(t['Action']=='pass' for t in run['tests'])
    routes=[]
    payload=('ReadBytes','CopyBytes','HashBytes','ZeroBytes','WriteBytes','AllocBytes')
    for run in ('component','component-race'):
        entries={x['name']:x['value'] for x in r['evidence'] if x['run']==run}
        for route in ('dirty','inherited','zero','mixed'):
            v=entries['routes/'+route]
            phases={}
            for phase in ('freeze','acquire'):
                selected=[c for k,c in v.items() if k.startswith(phase+'/')]
                assert selected
                totals={key:sum(c[key] for c in selected) for key in (*payload,'Metadata')}
                assert all(totals[key]==0 for key in payload)
                assert totals['Metadata']>0
                phases[phase]=totals
            if route in ('dirty','inherited'):
                assert v['application-read/'+route]['ReadBytes']>0
            if route in ('zero','mixed'):
                assert v['application-read/zero']['ZeroBytes']>0
            assert v['strict/content']['HashBytes']==3*16384+3
            routes.append({'run':run,'route':route,'phases':phases,'positive_controls':'PASS'})
        assert entries['internal-corruption-limit']['ownership_acquire']=='NOT DETECTED'
        assert entries['internal-corruption-limit']['strict_oracle']=='REJECTED'
        assert entries['cost']['materialized_blocks']==1
        assert entries['cost']['parent_root_depth']==0
        mapped=entries['mapped']
        assert mapped['mapped-copy/dirty']['CopyBytes']==32771
        assert mapped['mapped-source/mapped']['HashBytes']==32771
        assert mapped['mapped-target-verify/content']['HashBytes']==32771
        handoff=entries['handoff']
        assert handoff['handoff-send/handoff']['HashBytes']==16387
        assert handoff['handoff-receive/handoff']['HashBytes']==32774 # normal + corrupt attempt
        assert handoff['handoff-copy/dirty']['CopyBytes']==16387
    g0=json.loads((out/'g0-targeted.json').read_text())
    assert g0['exit_code']==0
    g0events=[json.loads(line) for line in (out/'g0-targeted.jsonl').read_text().splitlines()]
    assert any(e.get('Action')=='pass' and e.get('Test')=='TestG0VerifiedRootHandoff' for e in g0events)
    initial=[json.loads(line) for line in (out/'initial-component.jsonl').read_text().splitlines()]
    assert any(e.get('Action')=='pass' and 'Test' not in e for e in initial)
    summary={'component_source_commit':r['source_commit'],'G0_test_source_commit':g0['source_commit'],
             'runs':[{k:x[k] for k in ('name','exit_code','cgo_enabled')}|{'test_events':len(x['tests'])} for x in r['runs']],
             'routes':routes,'mapped':'PASS: actual macOS mapping, independent copy and strict check; not zero',
             'handoff':'PASS: in-memory adapter and existing manifest JSON decode; production IPC/FD/path route NOT RUN',
             'G0':'PASS in common-root component: strict hash 8 bytes, acquisition adds zero payload work; existing Heap optimization NOT IMPLEMENTED',
             'G1':'PASS in component: no Snapshot-only content reconstruction, no source/target hash in Freeze/Acquire',
             'G2':'PARTIAL: common sparse-block heap representation; mapped materialization remains a separate copy',
             'internal_corruption':'LIMITATION CONFIRMED: no-hash acquisition does not detect direct private-byte mutation; strict oracle rejects it',
             'platforms':{'macOS arm64':'PASS for bounded fixtures','Ubuntu x86_64':'SKIP: not executed'},
             'first_attempt':'Component tests PASS; collector failed on split test2json line. Raw evidence preserved; fixed runner then completed remaining checks.',
             'not_proven':['real guest integration','real SQL/workflow speed','production capture cancellation/retry and FD/relative-open wiring','production handoff transport','general memory/race correctness','acceptance of contract/detection changes']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PASS: evidence hashes, per-route zero/positive controls, strict limits, G0, mapped and handoff checks.')

if __name__=='__main__':main()
