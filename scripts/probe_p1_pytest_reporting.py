#!/usr/bin/env python3
"""Characterize existing pytest fixture failures; not P1 runtime acceptance."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

from git_identity import require_commit

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ('scripts/probe_p1_pytest_reporting.py', 'tests/test_routing_pytest.py',
          'python/mariamem/pytest_plugin.py', 'python/mariamem/__init__.py',
          'python/mariamem/snapshot.py')
REPORTER = '''
import json
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    failures = []
    seen = set()
    def walk(error):
        if error is None or id(error) in seen:
            return
        seen.add(id(error))
        failures.append({"type": type(error).__name__, "message": str(error),
            "notes": list(getattr(error, "__notes__", ())),
            "entry_fields": [name for name in ("stage", "admission_state", "cleanup_state")
                             if hasattr(error, name)]})
        walk(error.__cause__)
        walk(error.__context__)
        for child in getattr(error, "exceptions", ()):
            walk(child)
    if call.excinfo is not None:
        walk(call.excinfo.value)
    with Path('reports.jsonl').open('a') as output:
        output.write(json.dumps({"node": item.name, "phase": report.when,
            "outcome": report.outcome, "exceptions": failures}) + '\\n')
'''
TESTS = '''
def test_first(mariamem_fork):
    record_body('first')
    assert mariamem_fork.data.get('seed') == 1
    if MODE in ('ordinary-failure', 'child-cleanup-debt'):
        mariamem_fork.data['changed'] = True
        mariamem_fork.data['cleanup_failure'] = MODE == 'child-cleanup-debt'
        raise AssertionError('PRIMARY_TEST_FAILURE')

def test_second(mariamem_fork):
    record_body('second')
    assert mariamem_fork.data == {'seed': 1}
'''
ANNOTATION_HOOK = """
@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    outcome = yield
    if fixturedef.argname == 'mariamem_prepare' and outcome.excinfo is not None:
        outcome.excinfo[1].add_note(
            'P1_PROBE_NOTE: stage=prepare; admission=stopped; cleanup=pending')
"""
MODES = ('healthy' , 'ordinary-failure', 'child-cleanup-debt',
         'callback-and-source-failure', 'fixture-and-source-failure',
         'capture-and-source-failure', 'annotated-fixture-and-source-failure')


def need(value, reason):
    if not value:
        raise ValueError(reason)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def fake_runtime():
    tree = ast.parse((ROOT / 'tests/test_routing_pytest.py').read_text())
    source = next(ast.literal_eval(node.value) for node in tree.body
                  if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'FAKE_RUNTIME' for t in node.targets))
    replacements = {
        "        record('source.close')": "        record('source.close')\n        if MODE.endswith('and-source-failure'):\n            raise RuntimeError('SOURCE_CLEANUP_FAILURE')",
        "            record('child.close')": "            record('child.close')\n            if child.data.get('cleanup_failure'):\n                raise RuntimeError('CHILD_CLEANUP_FAILURE')",
        "        self.closed = True\n        try:\n            yield Baseline(self.data)": "        self.closed = True\n        if self.data.get('fail_capture'):\n            raise LookupError('PRIMARY_CAPTURE_FAILURE')\n        try:\n            yield Baseline(self.data)",
    }
    for before, after in replacements.items():
        need(source.count(before) == 1, 'fake-runtime anchor changed')
        source = source.replace(before, after)
    return source


def run_case(python, mode, output, runtime):
    with tempfile.TemporaryDirectory(prefix='mariamem-p1-report-') as name:
        directory = Path(name)
        preamble = 'MODE = ' + repr(mode) + '\n'
        preparation = '''
@pytest.fixture(scope='session')
def mariamem_prepare(mariamem_server):
    if MODE in ('fixture-and-source-failure', 'annotated-fixture-and-source-failure'):
        raise ValueError('PRIMARY_FIXTURE_FAILURE')
    def prepare(db):
        record('prepare')
        if MODE == 'callback-and-source-failure':
            raise ValueError('PRIMARY_PREPARE_FAILURE')
        db.data['seed'] = 1
        if MODE == 'capture-and-source-failure':
            db.data['fail_capture'] = True
        return 'ignored-result'
    return prepare
'''
        (directory / 'conftest.py').write_text(preamble + runtime + REPORTER + preparation
            + (ANNOTATION_HOOK if mode != 'fixture-and-source-failure' else ''))
        (directory / 'test_case.py').write_text(preamble + '''
from pathlib import Path

def record_body(name):
    with Path('bodies.txt').open('a') as output:
        output.write(name + '\\n')
''' + TESTS)
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('PYTEST_', 'PYTHON', 'MARIAMEM_', 'MYSQLMEM_'))}
        env.update(PYTHONPATH=str(ROOT / 'python'), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                   PYTHONDONTWRITEBYTECODE='1')
        argv = [str(python), '-m', 'pytest', '-p', 'mariamem.pytest_plugin', '-q', '--tb=short']
        result = subprocess.run(argv, cwd=directory, env=env, text=True, capture_output=True, timeout=30)
        (output / (mode + '.txt')).write_text(result.stdout + result.stderr)
        reports = [json.loads(line) for line in (directory / 'reports.jsonl').read_text().splitlines()]
        bodies = (directory / 'bodies.txt').read_text().splitlines() if (directory / 'bodies.txt').exists() else []
        events = [json.loads(line) for line in (directory / 'events-main.jsonl').read_text().splitlines()]
        write(output / (mode + '-reports.json'), reports)
        errors = [error for row in reports for error in row['exceptions']]
        messages = {e['message'] for e in errors}
        need(result.returncode == (0 if mode == 'healthy' else 1), mode + ': unexpected pytest exit')
        need(events.count('start') == events.count('source.close') == 1, mode + ': source census')
        if mode.endswith('and-source-failure'):
            primary = {'callback-and-source-failure': 'PRIMARY_PREPARE_FAILURE',
                       'fixture-and-source-failure': 'PRIMARY_FIXTURE_FAILURE',
                       'annotated-fixture-and-source-failure': 'PRIMARY_FIXTURE_FAILURE',
                       'capture-and-source-failure': 'PRIMARY_CAPTURE_FAILURE'}[mode]
            need({primary, 'SOURCE_CLEANUP_FAILURE'} <= messages, mode + ': original/cleanup not retained')
            need(not bodies and 'fork' not in events, mode + ': dependent body admitted')
        else:
            need(bodies == ['first', 'second'], mode + ': healthy next-child census')
            need(events.count('prepare') == events.count('snapshot') == 1, mode + ': preparation repeated')
            need(events.count('fork') == events.count('child.close') == 2, mode + ': child census')
        notes = [note for error in errors for note in error['notes']]
        if mode == 'annotated-fixture-and-source-failure':
            need(notes and all(note.startswith('P1_PROBE_NOTE:') for note in notes)
                 and 'P1_PROBE_NOTE:' in result.stdout, 'narrow note not rendered')
        else:
            need(not notes, mode + ': unrelated operation was annotated')
        if mode == 'child-cleanup-debt':
            need({'PRIMARY_TEST_FAILURE', 'CHILD_CLEANUP_FAILURE'} <= messages, 'both test/cleanup errors missing')
            need(any(r['node'] == 'test_first' and r['phase'] == 'teardown'
                     and r['outcome'] == 'failed' for r in reports), 'cleanup failure not reported')
        return {'mode': mode, 'exit_code': result.returncode, 'bodies': bodies,
                'events': events, 'errors': errors,
                'later_body_after_cleanup_failure': mode == 'child-cleanup-debt' and 'second' in bodies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require_commit(ROOT, args.expected_source_commit)
    need(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
         == args.expected_source_commit, 'HEAD differs from expected source')
    need(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT), 'requires clean source')
    args.output.mkdir(parents=True, exist_ok=False)
    python = args.python.absolute()
    profile = json.loads(subprocess.check_output([str(python), '-c',
        'import sys,pytest,json; print(json.dumps({"python":sys.version,"pytest":pytest.__version__}))'], text=True))
    result = {'result': 'RUNNING', 'source_commit': args.expected_source_commit,
              'scope': 'existing pytest control flow with fake DB owners; no guest/SQL/P1 acceptance',
              'host': {'system': platform.system(), 'version': platform.mac_ver()[0], 'architecture': platform.machine()},
              'profile': profile, 'inputs_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in INPUTS}}
    try:
        runtime = fake_runtime()
        result['cases'] = [run_case(python, mode, args.output, runtime) for mode in MODES]
        need(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT), 'source became dirty')
        result['result'] = 'CHARACTERIZATION_PASS'
    finally:
        write(args.output / 'result.json', result)
        write(args.output / 'SHA256SUMS.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in args.output.iterdir() if p.is_file() and p.name != 'SHA256SUMS.json'})
    print('PYTEST_REPORT_CHARACTERIZATION_PASS (not P1 runtime acceptance)')


if __name__ == '__main__':
    main()
