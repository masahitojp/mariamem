"""Bounded native -> ordinary guest -> two independent Fork comparisons."""
import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
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
    assert observed['baseline_rows'] == expected_rows, observed
    assert observed['original_sentinel'] == [[17]], observed
    assert observed['test_schema_count_after'] == int(reuse), observed
    if runner == 'manage':
        assert [e['event'] for e in events if 'databases_' in e['event']] == [
            'setup_databases_begin', 'setup_databases_end', 'teardown_databases_begin', 'teardown_databases_end'], observed
    return dict(result='PASS', **observed)


def campaign(info, original, target, output, reuse=False):
    results = []
    for runner, mode, reverse in CASES:
        name = runner + '-' + mode + ('-reverse' if reverse else '')
        results.append(run_case(info, original, target, runner, mode, reverse, output / name, reuse))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-port', type=int, required=True)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((HERE / 'input-manifest.json').read_text())
    for name, digest in manifest['application_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    for name, version in manifest['versions'].items():
        assert importlib.metadata.version(name) == version, name
    require_commit(ROOT, args.expected_source_commit)
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == args.expected_source_commit
    verify_go_binary(ROOT, args.host.resolve(), args.expected_source_commit)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    native = dict(host='127.0.0.1', port=args.native_port)
    assert query(native, 'SELECT VERSION()')[0][0].startswith('12.3.3-MariaDB')
    token = 'w3_' + uuid.uuid4().hex[:10]
    original, target = token, 'test_' + token
    assert re.fullmatch('[a-z0-9_]+', original + target)
    report = dict(source_commit=args.expected_source_commit, packages={n: importlib.metadata.version(n) for n in ('Django','mysqlclient','pytest','pytest-django')},
                  python=sys.version, routes={}, native_original_removed=False)
    try:
        initialize(native, original)
        report['routes']['native'] = campaign(native, original, target, output / 'native')
        # No guest route starts unless every native observation passed.
        import mariamem
        source = mariamem.start(host_binary=args.host.resolve())
        session = source._session
        try:
            info = source.connection_info()
            initialize(info, original)
            report['routes']['guest-standard'] = campaign(info, original, target, output / 'guest-standard')
            env = environment(info, original, target, output, 'prepare')
            prepared_run = subprocess.run([sys.executable, str(HERE / 'prepare.py')], env=env,
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            (output / 'preparation.txt').write_bytes(prepared_run.stdout)
            assert prepared_run.returncode == 0, prepared_run.stdout.decode(errors='replace')
            source.wait_disconnected()
            with source.snapshot() as saved:
                report['source_consumed'] = source.closed
                for copy in (1, 2):
                    observations = []
                    for runner, mode, reverse in CASES:
                        name = runner + '-' + mode + ('-reverse' if reverse else '')
                        with saved.fork() as child:
                            child_info = child.connection_info()
                            assert query(child_info, 'SELECT sku,quantity,status FROM orders_order', database=target) == (('SEED',2,'ready'),)
                            observations.append(run_case(child_info, original, target, runner, mode, reverse,
                                                         output / f'fork-{copy}' / name, True))
                    report['routes'][f'fork-{copy}'] = observations
        finally:
            source.close()
            report['guest_host_reaped'] = session._process.poll() is not None
            report['guest_temp_removed'] = not session.root.exists()
        assert report['source_consumed'] and report['guest_host_reaped'] and report['guest_temp_removed']
        report['result'] = 'PASS_LOCAL_DJANGO_LIFECYCLE'
    finally:
        query(native, f'DROP DATABASE IF EXISTS `{target}`')
        query(native, f'DROP DATABASE IF EXISTS `{original}`')
        report['native_original_removed'] = schemas(native, original) == 0 and schemas(native, target) == 0
        write(output / 'result.json', report)
    assert report['native_original_removed']
    print(json.dumps(dict(result=report['result'], suites=sum(map(len, report['routes'].values())), python=sys.version.split()[0])))


if __name__ == '__main__':
    main()
