"""Finite experiment oracles. Preserve raw failures, especially full-fix1193."""
import hashlib
import json
from pathlib import Path
import statistics
import sys
from collections import Counter

ev = Path(sys.argv[1])
load = lambda n: json.loads((ev/n).read_text())
native = load('native-final-baseline.json')
guest = {m: load('guest-'+m+'.json') for m in ['baseline','proc-only','damaged-proc','base-fix']}
rows = []
def record(name, result, **detail): rows.append(dict(check=name,result=result,**detail))
def normalized(x):
    if isinstance(x, dict):
        return {k:normalized(v) for k,v in x.items() if k not in ('elapsed_ms','error')}
    if isinstance(x, list): return [normalized(v) for v in x]
    return x
def compare(cases):
    assert len(cases)==len(native['routines'])==6
    assert all(r['result']=='PASS' for r in cases)
    assert normalized(cases)==normalized(native['routines'])
    return 6
base = guest['baseline']
assert next(x for x in base['before'] if x['sql'].startswith('CREATE PROCEDURE'))['errno']==1146
assert all(r['result']=='FAIL' and '1146' in r['error'] for r in base['routines'])
record('initial-missing-proc-negative-oracle','PASS',actual_errno=1146)
record('initial-routines-unavailable','FAIL',actual_errno=1146,meaning='expected unrepaired state; retained')
record('official-proc-only-routines-native-parity','PASS',cases=compare(guest['proc-only']['routines']))
damaged = guest['damaged-proc']
bad = next(s for s in damaged['stages'] if s['stage']=='controlled-wrong-nullability')
assert bad['steps'][0]['result']=='PASS' and bad['steps'][1]['errno']==1728
assert "expected column 'comment' at position 15 to be NOT NULL" in damaged['before_fix_logs']
assert all(r['result']=='FAIL' and '1728' in r['error'] for r in damaged['routines'])
record('controlled-definition-mismatch-negative-oracle','PASS',actual_errno=1728,ordinal=15,column='comment',reason='NOT NULL required')
record('definition-repair-restores-native-parity','PASS',cases=compare(damaged['after_repair']))
full = guest['base-fix']
assert len(full['stages'][0]['steps'])==89 and all(s['result']=='PASS' for s in full['stages'][0]['steps'])
record('official-base-all-statements','PASS',statements=89,cases=compare(full['base_routines']))
allowed = set(load('upstream-upgrade-error-policy.json')['expected_error_codes'])
for name,d in [('guest',full),('native',load('native-final-base-fix.json'))]:
    steps=next(s['steps'] for s in d['stages'] if s['stage']=='fix')
    errors=[s for s in steps if s['result']=='FAIL']
    unexpected=[s for s in errors if s['errno'] not in allowed]
    if name=='guest':
        assert len(errors)==87 and len(unexpected)==1
        assert unexpected[0]['errno']==1193 and unexpected[0]['sql']=='set global event_scheduler=original'
    else: assert not unexpected
    record(name+'-official-fix-upgrade-policy','FAIL' if unexpected else 'PASS',statements=len(steps),raw_failures=len(errors),error_counts=dict(Counter(s['errno'] for s in errors)),unexpected=unexpected)
record('routines-after-full-fix-despite-1193','PASS',cases=compare(full['routines']),does_not_resolve='guest-official-fix-upgrade-policy FAIL')
assert all(d['events']['errno']==1235 for d in guest.values())
record('events-remain-unsupported','PASS',actual_errno=1235,meaning='unsupported boundary confirmed; not feature support')
for check,why in [('historical-web-repl-1728-cause','exact manual DDL, server error log and deployed binary identity were not supplied; controlled WASIX reproduction is not attribution'),('emscripten-deployed-binary-equivalence','fixed lite4 source definition equality established; deployed Web REPL provenance not available'),('native-ubuntu-x86_64','local machine is macOS arm64; reference container is Linux arm64'),('embedded-sql-binary-size-startup','no embedding/code change made; only unchanged Wasm + runtime SQL measured')]:
    record(check,'SKIP',reason=why)
assert load('translation-vs-reviewed.json')['raw_files_equal_previous']
assert load('runtime-vs-reviewed.json')['changed']==['provenance.json']
dev=load('development.json')
assert dev['smoke']=='PASS' and dev['result']=='UNQUALIFIED'
assert dev['binary_sha256']=='f779d6a4e092c9dddbc9a27b7f225cf8466031105c6ce3dc7b7ef2efe7a44b89'
record('fresh-build-generation-vs-reviewed','PASS',guest_sha256=dev['guest_sha256'],binary_sha256=dev['binary_sha256'],manifest_files=51,raw_module_files=52,runtime_files_equal=98,provenance='original new input record retained')
record('official-development-smoke','PASS',qualification='UNQUALIFIED')
cost = {}
for mode in ['control','proc','base-fix']:
    samples=load('cost-'+mode+'.json')['samples']
    assert len(samples)==3
    if mode!='base-fix': assert all(not s['init_errors'] for s in samples)
    else: assert all(len(s['init_errors'])==87 for s in samples)
    cost[mode]=dict(n=3,first_start_ms=samples[0]['start_ms'],first_init_ms=samples[0]['init_ms'],later_start_median_ms=statistics.median(s['start_ms'] for s in samples[1:]),later_init_median_ms=statistics.median(s['init_ms'] for s in samples[1:]),init_range_ms=[min(s['init_ms'] for s in samples),max(s['init_ms'] for s in samples)])
report=dict(feasibility='PASS',meaning='minimum text-SQL procedure/function cases feasible after pinned proc DDL; not full install-db, production support or prepared CALL',matrix=rows,cost_diagnostic=cost)
(ev/'assessment.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(feasibility=report['feasibility'],checks=len(rows),cost=cost),indent=2))
