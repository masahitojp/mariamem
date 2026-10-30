#!/usr/bin/env python3
"""Bounded example command timings; no cold-machine or resource claims."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from git_identity import require_commit

ROOT = Path(__file__).resolve().parents[1]


def run(expected, output, include_go=False):
    require_commit(ROOT, expected)
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() != expected:
        raise ValueError('wrong source')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = dict(source_commit=expected, result='RUNNING', commands=[],
                  acquisition='existing CI toolchain/dependencies/cache; cold setup unmeasured',
                  human_edit_seconds=None,
                  second_test_edit='add second case name to the existing parametrization; no additional lifecycle block',
                  phase='whole test-command wall time, including its setup/cases/cleanup; not an isolated Reset benchmark')
    report['second_test_edits'] = {
        'python': {'path': 'docs/examples/e2e_owned/python/test_orders.py', 'before': '["first"]', 'after': '["first", "second"]'},
        'go': {'path': 'docs/examples/e2e_owned/go/entry_test.go', 'before': '[]string{"first"}', 'after': '[]string{"first", "second"}'}}
    for edit in report['second_test_edits'].values():
        if (ROOT/edit['path']).read_text().count(edit['after']) != 1:
            raise ValueError('second-test edit anchor changed')
    try:
        for stage in ('first', 'second', 'repeat'):
            junit = output/(stage+'.xml')
            command = [sys.executable, '-m', 'pytest', 'docs/examples/e2e_owned/python/test_orders.py',
                       '-q', '--junitxml='+str(junit)]
            if stage == 'first': command += ['-k', 'first']
            commands = [('python', command)]
            if include_go:
                selector = '^TestOwnedOrders$/^first$' if stage == 'first' else '^TestOwnedOrders$'
                commands.append(('go', ['go', 'test', '-p', '1', './docs/examples/e2e_owned/go', '-run', selector, '-count=1', '-json']))
            for language, argv in commands:
                began = time.monotonic()
                log = output/(language+'-'+stage+'.txt')
                with log.open('w') as stream:
                    p = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
                row = dict(language=language, stage=stage, command=argv, elapsed_seconds=time.monotonic()-began, returncode=p.returncode)
                report['commands'].append(row)
                if p.returncode: raise ValueError('example failed: '+log.name)
                count = 1 if stage == 'first' else 2
                if language == 'python':
                    cases = ET.parse(junit).findall('.//testcase')
                    if len(cases) != count or any(c.find(tag) is not None for c in cases for tag in ('skipped', 'failure', 'error')):
                        raise ValueError('Python case census differs')
                else:
                    events = [json.loads(line) for line in log.read_text().splitlines()]
                    names = {'TestOwnedOrders', 'TestOwnedOrders/first'}
                    if count == 2: names.add('TestOwnedOrders/second')
                    passed = {e.get('Test') for e in events if e.get('Action') == 'pass' and e.get('Test')}
                    if passed != names or any(e.get('Action') in ('skip', 'fail') for e in events):
                        raise ValueError('Go case census differs')
        report['inputs_sha256'] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ('docs/examples/e2e_owned/python/test_orders.py', 'docs/examples/e2e_owned/go/entry_test.go', 'scripts/e2e_workflow_timing.py')}
        report['result'] = 'PASS_BOUNDED_WORKFLOW'
    except Exception as error:
        report['result'], report['error'] = 'FAIL', str(error)
        raise
    finally:
        (output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--include-go', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.expected_source_commit, args.output, args.include_go), indent=2))
