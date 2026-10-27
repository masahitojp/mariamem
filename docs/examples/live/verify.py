"""Execute the public examples against exact-source acceptance executables."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import inspect_ref, require_commit, verify_go_binary


def python_passed(path):
    suites = ET.parse(path).getroot().findall('.//testsuite')
    counts = {key: sum(int(s.get(key, 0)) for s in suites)
              for key in ('tests', 'errors', 'failures', 'skipped')}
    return counts == dict(tests=2, errors=0, failures=0, skipped=0)


def go_passed(path):
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    terminal = {(e.get('Test'), e['Action']) for e in events
                if e['Action'] in ('pass', 'fail', 'skip')}
    return (all((name, 'pass') in terminal for name in
                ('TestOrders', 'TestOrders/first', 'TestOrders/second'))
            and not any(action in ('fail', 'skip') for _, action in terminal))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--go-app', type=Path, required=True)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = require_commit(ROOT, args.expected_source_commit).source_commit
    assert inspect_ref(ROOT, 'HEAD').source_commit == source, 'checkout differs from candidate'
    binaries = {name: verify_go_binary(ROOT, path.resolve(), source)
                for name, path in [('host', args.host), ('go_app', args.go_app)]}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = list((ROOT / 'docs/examples/live').rglob('*.py')) + [
        ROOT / 'docs/examples/live/go/live_test.go',
        ROOT / 'tests/live_acceptance/goapp/main.go',
        ROOT / 'tests/e2e_native_control/goapp/schema.sql',
    ] + list((ROOT / 'tests/e2e_native_control/pythonapp').rglob('*.py'))
    report = dict(result='FAIL', source_commit=source, python=sys.version,
                  binary_identity=binaries,
                  input_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(inputs)}, runs={})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTEST_ADDOPTS='', PYTHONPATH=str(ROOT / 'python'),
               MARIAMEM_HOST_BINARY=str(args.host.resolve()),
               MARIAMEM_RUN_LIVE_EXAMPLES='1', E2E_GO_APP=str(args.go_app.resolve()))
    commands = {
        'go': ['go', 'test', '-p', '1', '-count=1', '-json', './docs/examples/live/go'],
        'python': [sys.executable, '-m', 'pytest', 'docs/examples/live/python/test_orders.py',
                   '-v', '--basetemp', str(output / 'pytest-temp'),
                   '--junitxml', str(output / 'pytest.xml')],
    }
    try:
        for name, command in commands.items():
            log = output / (name + '.txt')
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=300)
            passed = result.returncode == 0 and (go_passed(log) if name == 'go'
                                                else python_passed(output / 'pytest.xml'))
            report['runs'][name] = dict(result='PASS' if passed else 'FAIL',
                                        command=command, exit_code=result.returncode)
        if all(r['result'] == 'PASS' for r in report['runs'].values()):
            report['result'] = 'PASS_PUBLIC_EXAMPLES'
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['result'] == 'PASS_PUBLIC_EXAMPLES' else 1


if __name__ == '__main__':
    raise SystemExit(main())
