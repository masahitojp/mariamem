"""Selected standard-runner lifecycle oracles; invoked by ci.py."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import require_commit, verify_go_binary

CASES = [('manage', 'atomic', False), ('manage', 'atomic', True),
         ('manage', 'serialized', False), ('manage', 'serialized', True),
         ('manage', 'flush', False), ('manage', 'failure', False),
         ('pytest', 'atomic', False), ('pytest', 'serialized', False),
         ('pytest', 'flush', False), ('pytest', 'failure', False)]
CLASSES = dict(atomic='AtomicCases', serialized='SerializedCases', flush='FlushCases', failure='FailureCases')


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def connect(info, database=''):
    import MySQLdb
    return MySQLdb.connect(host=info['host'], port=info['port'], user='root', passwd='',
                           db=database, autocommit=True, charset='utf8mb4', connect_timeout=3)


def query(info, sql, args=(), database=''):
    with contextlib.closing(connect(info, database)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchall()


def schemas(info, name):
    return query(info, 'SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=%s', (name,))[0][0]


def environment(info, original, target, out, mode):
    return dict(os.environ, E2E_DB_HOST=info['host'], E2E_DB_PORT=str(info['port']),
                E2E_DB_NAME=original, W3_TEST_NAME=target, W3_MODE=mode, W3_RUN='1',
                DJANGO_SETTINGS_MODULE='lifecycle_settings', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                PYTHONPATH=os.pathsep.join([str(HERE), str(ROOT / 'tests/e2e_native_control/pythonapp'), str(ROOT / 'python')]),
                W3_EVENTS=str(out / 'events.jsonl'), W3_SUMMARY=str(out / 'summary.json'))


def initialize(info, original):
    query(info, f'CREATE DATABASE `{original}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    query(info, 'CREATE TABLE sentinel (n INT PRIMARY KEY)', database=original)
    query(info, 'INSERT INTO sentinel VALUES (17)', database=original)


def run_case(info, original, target, runner, mode, reverse, out, reuse):
    out.mkdir(parents=True)
    env = environment(info, original, target, out, mode)
    if runner == 'manage':
        argv = [sys.executable, str(ROOT / 'tests/e2e_native_control/pythonapp/manage.py'),
                'test', 'cases.' + CLASSES[mode], '--noinput', '--verbosity=2']
        if reverse:
            argv.append('--reverse')
        if reuse:
            argv.append('--keepdb')
    else:
        selected = 'serialized' if mode == 'failure' else mode
        argv = [sys.executable, '-m', 'pytest', '-p', 'pytest_django.plugin',
                str(HERE / 'test_pytest_cases.py'), '-k', selected, '-v',
                '--junitxml=' + str(out / 'pytest.xml')]
        if reuse:
            argv.append('--reuse-db')
    result = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (out / 'stdout.txt').write_bytes(result.stdout)
    if runner == 'manage':
        summary = json.loads((out / 'summary.json').read_text())
    else:
        tree = ET.parse(out / 'pytest.xml').getroot()
        suites = tree.findall('.//testsuite')
        counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
        summary = dict(tests=counts['tests'], passed=counts['tests']-counts['failures']-counts['errors']-counts['skipped'],
                       failures=[dict(name=t.get('name'), message=(f.get('message', '') + (f.text or '')))
                                 for t in tree.findall('.//testcase') for f in t.findall('failure')],
                       errors=[t.get('name') for t in tree.findall('.//testcase') if t.find('error') is not None], skipped=counts['skipped'])
        write(out / 'summary.json', summary)
    events = [json.loads(line) for line in (out / 'events.jsonl').read_text().splitlines()]
    baseline = [event for event in events if event['event'] == 'case_baseline']
    expected_rows = [[['SEED', 2, 'ready']]] * 2
    if runner == 'manage' and mode == 'atomic':
        expected_rows = [[['SEED', 2, 'ready'], ['CLASS', 1, 'ready']]] * 2
    elif mode == 'flush':
        expected_rows = [[['SEED', 2, 'ready']], []]
    expected_failure = mode == 'failure'
    observed = dict(runner=runner, mode=mode, reverse=reverse, reuse=reuse, exit_code=result.returncode,
                    summary=summary, baseline_rows=[event['rows'] for event in baseline],
                    test_schema_count_after=schemas(info, target),
                    original_sentinel=[list(r) for r in query(info, 'SELECT n FROM sentinel', database=original)])
    write(out / 'observed.json', observed)
    assert summary['tests'] == 2 and not summary['errors'] and summary['skipped'] == 0, observed
    assert summary['passed'] == (1 if expected_failure else 2), observed
    assert len(summary['failures']) == (1 if expected_failure else 0), observed
    assert result.returncode == (1 if expected_failure else 0), observed
    if expected_failure:
        assert 'W3_EXPECTED_FAILURE_AFTER_COMMIT' in summary['failures'][0]['message'], observed
        assert summary['failures'][0]['name'].endswith('test_01_commit' if runner == 'manage' else 'test_serialized[0]'), observed
    assert observed['baseline_rows'] == expected_rows, observed
    assert observed['original_sentinel'] == [[17]], observed
    assert observed['test_schema_count_after'] == int(reuse), observed
    if runner == 'manage':
        assert [e['event'] for e in events if 'databases_' in e['event']] == [
            'setup_databases_begin', 'setup_databases_end', 'teardown_databases_begin', 'teardown_databases_end'], observed
    return dict(result='PASS', **observed)
