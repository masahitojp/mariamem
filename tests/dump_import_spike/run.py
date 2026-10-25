"""Run the bounded import/lifecycle matrix; functional FAILs are retained."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET

from routes import CANONICAL_SHA256, input_bytes
from bind_input import check_binding
from linux_acquisition import source_identity

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def assess(route, mode, code, counts, events, contacts):
    def named(name):
        return [event for event in events if event['event'] == name]
    if contacts or len(named('source_start')) != 1 or len(named('prepare_start')) != 1:
        return False
    clean = named('source_cleanup')
    if len(clean) != 1 or not all(clean[0].get(k) is True for k in ['closed', 'host_reaped', 'directory_removed']):
        return False
    if len(named('preparation_connections_closed')) != 1:
        return False
    if mode == 'success':
        passed = named('test_pass')
        return (code == 0 and counts == {'tests': 2, 'errors': 0, 'failures': 0, 'skipped': 0}
                and len(named('prepared_state')) == 1 and named('prepared_state')[0].get('reference_equal') is True
                and len(named('snapshot_attempt')) == len(named('snapshot_success')) == 1
                and len(named('preparation_disconnected')) == 1
                and named('preparation_disconnected')[0].get('active_connections') == 0
                and len(passed) == 2 and len({e['child'] for e in passed}) == 2
                and {e['name'] for e in passed} == {'commit', 'independent_initial_state'}
                and not named('prepare_error'))
    if code != 1 or counts != {'tests': 2, 'errors': 2, 'failures': 0, 'skipped': 0}:
        return False
    if any(named(name) for name in ['prepared_state', 'snapshot_attempt', 'snapshot_success', 'test_pass']):
        return False
    errors, partial = named('prepare_error'), named('partial_source_state')
    if len(errors) != 1 or len(partial) != 1:
        return False
    error = errors[0]
    if error.get('route') != route or error.get('mode') != mode:
        return False
    location = error.get('location', {})
    start, end = location.get('byte_start'), location.get('byte_end')
    if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(input_bytes(mode))
            and isinstance(location.get('line_start'), int) and location['line_start'] >= 1):
        return False
    if route == 'reader':
        if not isinstance(location.get('ordinal'), int) or location['ordinal'] < 1:
            return False
        if mode == 'sql_failure':
            return (error.get('stage') == 'execute' and error.get('reason') == 'sql_error'
                    and error.get('errno') == 1146 and error.get('original_exception') == 'ProgrammingError'
                    and 'spike_partial' in partial[0].get('tables', [])
                    and start <= input_bytes(mode).index(b'INSERT INTO missing_dump_oracle') < end)
        expected = {'malformed': 'unterminated_quote', 'source': 'unsupported_client_command'}[mode]
        return (error.get('stage') == 'preflight' and error.get('reason') == expected
                and error.get('errno') is None and partial[0].get('tables') == [])
    if error.get('stage') != 'native_client' or not error.get('exit_code') or 'users' not in partial[0].get('tables', []):
        return False
    if mode == 'sql_failure':
        return (error.get('reason') == 'native_client_error'
                and error.get('errno') == 1146 and error.get('sqlstate') == '42S02'
                and 'spike_partial' in partial[0]['tables']
                and start <= input_bytes(mode).index(b'INSERT INTO missing_dump_oracle') < end)
    if mode == 'malformed':
        return (error.get('reason') == 'native_client_error'
                and error.get('errno') == 1064 and error.get('sqlstate') == '42000')
    return error.get('reason') == 'sandbox_rejected_client_command'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--host-source', required=True)
    parser.add_argument('--client-command', required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--binding', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT/'scripts'))
    from git_identity import require_commit, verify_go_binary
    identity = require_commit(ROOT, args.host_source)
    source_identity(identity.source_commit)
    binding = check_binding(args.binding, identity.source_commit)
    original = dict(os.environ)
    try:
        os.environ['GOTOOLCHAIN'] = 'go1.26.10'
        buildinfo = verify_go_binary(ROOT, args.host.resolve(), identity.source_commit)
    finally:
        os.environ.clear()
        os.environ.update(original)
    reference = json.loads(args.reference.read_text())
    assert reference['result'] == 'PASS' and reference['dump_sha256'] == CANONICAL_SHA256
    assert reference['source_commit'] == identity.source_commit and reference['binding'] == binding
    assert sys.version_info[:2] in [(3, 11), (3, 14)]
    assert {name: importlib.metadata.version(name) for name in ['pytest', 'PyMySQL', 'SQLAlchemy']} == {
        'pytest': '7.0.0' if sys.version_info[:2] == (3, 11) else '9.0.2',
        'PyMySQL': '1.2.3', 'SQLAlchemy': '2.0.54'}
    # Reuse the stable sentinel only; no xdist/framework census is rerun.
    spec = importlib.util.spec_from_file_location('migration_runner', ROOT/'tests/preparation_migration_acceptance/run.py')
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    sentinel = owner.Sentinel()
    report = {'result': 'FAIL', 'dump_sha256': CANONICAL_SHA256,
        'source_commit': json.loads(subprocess.check_output(
            ['python3', 'scripts/git_identity.py', 'inspect', 'HEAD'], cwd=ROOT, text=True))['source_commit'],
        'host_source_commit': identity.source_commit, 'host_buildinfo': buildinfo,
        'host_sha256': hashlib.sha256(args.host.read_bytes()).hexdigest(),
        'guest_sha256': json.loads((ROOT/'release/generated-go-inputs.json').read_text())['guest_sha256'],
        'binding': binding,
        'platform': platform.platform(), 'python': sys.version,
        'packages': {name: importlib.metadata.version(name) for name in ['pytest', 'PyMySQL', 'SQLAlchemy']},
        'runs': {}}
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT/'python'), str(HERE),
        str(ROOT/'tests/preparation_migration_acceptance')]),
        PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTEST_ADDOPTS='',
        MIGRATION_HOST=str(args.host.resolve()), MIGRATION_ORIGINAL_PORT=str(sentinel.port),
        DUMP_CLIENT=args.client_command, DUMP_REFERENCE=str(args.reference.resolve()))
    try:
        # Both successful lifecycle cases precede the failure/admission matrix.
        for modes in [['success'], ['sql_failure', 'malformed', 'source']]:
            for route, mode in [(route, mode) for route in ['native', 'reader'] for mode in modes]:
                label = route+'-'+mode
                directory = out/label
                directory.mkdir()  # Refuse stale receipts.
                scenario_env = dict(env, DUMP_ROUTE=route, DUMP_MODE=mode, DUMP_OUTPUT=str(directory),
                                    MIGRATION_EVENTS=str(directory/'events.jsonl'))
                argv = [sys.executable, '-m', 'pytest', '-p', 'mariamem.pytest_plugin',
                    '--mariamem-route', f'app=127.0.0.1:{sentinel.port}/app',
                    str(HERE/'workflow.py'), '-q', '--tb=short', '--junitxml', str(directory/'pytest.xml')]
                before = sentinel.contacts
                with (directory/'pytest.txt').open('w') as log:
                    process = subprocess.Popen(argv, cwd=ROOT, env=scenario_env, stdout=log,
                                               stderr=subprocess.STDOUT, start_new_session=True)
                    try:
                        code = process.wait(timeout=180)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()
                        raise RuntimeError(label+': timeout, no PASS')
                events = [json.loads(line) for p in directory.glob('events-*.jsonl')
                          for line in p.read_text().splitlines()]
                suites = ET.parse(directory/'pytest.xml').getroot().findall('.//testsuite')
                counts = {key: sum(int(s.get(key, 0)) for s in suites)
                          for key in ['tests', 'errors', 'failures', 'skipped']}
                accepted = assess(route, mode, code, counts, events, sentinel.contacts-before)
                report['runs'][label] = dict(accepted=accepted, exit_code=code, counts=counts,
                    original_endpoint_contacts=sentinel.contacts-before)
                print(label, report['runs'][label], flush=True)
    finally:
        sentinel.close()
        report['original_endpoint_contacts'] = sentinel.contacts
        if len(report['runs']) == 8 and all(r['accepted'] for r in report['runs'].values()) and not sentinel.contacts:
            report['result'] = 'PASS'
        (out/'results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
