"""Mixed-order comparison, partial migration failure and runnable recipe checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import run as base

HERE, ROOT = base.HERE, base.ROOT
ORDERS = ['normal', 'reverse', 'shuffle-137', 'shuffle-911-reverse']


def events(out):
    p = out / 'events.jsonl'
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


def junit(path):
    root = ET.parse(path).getroot()
    return {key: sum(int(s.get(key, 0)) for s in root.findall('.//testsuite'))
            for key in ('tests', 'failures', 'errors', 'skipped')}


def command(runner, out, order='normal', reuse=False, admission=False):
    if runner == 'manage':
        argv = [sys.executable, str(ROOT / 'tests/e2e_native_control/pythonapp/manage.py'),
                'test', 'admission_cases.AdmissionCases' if admission else 'mixed_cases', '--noinput', '-v2']
        if order.endswith('reverse'):
            argv.append('--reverse')
        if order.startswith('shuffle'):
            argv.append('--shuffle=' + order.split('-')[1])
        if reuse:
            argv.append('--keepdb')
    else:
        path = HERE / ('admission_cases.py' if admission else 'test_mixed_cases.py')
        argv = [sys.executable, '-m', 'pytest', '-p', 'pytest_django.plugin', '-p', 'order_probe',
                str(path), '-v', '--junitxml=' + str(out / 'pytest.xml')]
        if reuse:
            argv.append('--reuse-db')
    return argv


def projection(values):
    return [{key: value for key, value in event.items() if key != 'database'}
            for event in values if event['event'] in ('test_started', 'case_baseline', 'commit_observed', 'atomic_recovery')]


def mixed(info, original, target, runner, order, out, reuse=False, reference=None):
    out.mkdir(parents=True)
    env = base.environment(info, original, target, out, 'mixed')
    env.update(W3_ORDER=order, W3_BROKEN_MIGRATION='0')
    result = subprocess.run(command(runner, out, order, reuse), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (out / 'stdout.txt').write_bytes(result.stdout)
    if runner == 'manage':
        summary = json.loads((out / 'summary.json').read_text())
        counts = dict(tests=summary['tests'], failures=len(summary['failures']),
                      errors=len(summary['errors']), skipped=summary['skipped'])
    else:
        counts = junit(out / 'pytest.xml')
    values = events(out)
    observed = dict(runner=runner, order=order, reuse=reuse, exit_code=result.returncode,
                    counts=counts, projection=projection(values),
                    test_schema_count_after=base.schemas(info, target),
                    original_sentinel=[list(row) for row in base.query(info, 'SELECT n FROM sentinel', database=original)])
    base.write(out / 'observed.json', observed)
    assert result.returncode == 0 and counts == dict(tests=6 if runner=='manage' else 12, failures=0, errors=0, skipped=0), observed
    assert len([v for v in values if v['event']=='case_baseline']) == counts['tests'], observed
    assert observed['test_schema_count_after'] == int(reuse) and observed['original_sentinel'] == [[17]], observed
    if reference is not None:
        assert observed['projection'] == reference['projection'], (runner, order, 'native event mismatch')
    return dict(result='PASS', **observed)


def failure(info, original, target, runner, out):
    out.mkdir(parents=True)
    env = base.environment(info, original, target, out, 'migration-failure')
    env.update(W3_BROKEN_MIGRATION='1', W3_ORDER='normal')
    result = subprocess.run(command(runner, out, admission=True), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (out / 'stdout.txt').write_bytes(result.stdout)
    values = events(out)
    failed = [v for v in values if v['event']=='setup_failed']
    observed = dict(runner=runner, exit_code=result.returncode, setup_failures=failed,
                    bodies_admitted=[v for v in values if v['event']=='test_body_admitted'],
                    partial_schema_count=base.schemas(info, target),
                    partial_ddl=base.query(info, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name='w3_partial_ddl'", (target,))[0][0],
                    migrations=[row[0] for row in base.query(info, "SELECT name FROM django_migrations WHERE app='orders' ORDER BY name", database=target)],
                    original_sentinel=[list(row) for row in base.query(info, 'SELECT n FROM sentinel', database=original)])
    if runner=='pytest':
        observed['junit'] = junit(out/'pytest.xml')
    base.write(out / 'observed.json', observed)
    assert result.returncode == 1 and not observed['bodies_admitted'], observed
    assert len(failed) == (1 if runner=='manage' else 2), observed
    for error in failed:
        assert [entry['type'] for entry in error['errors']][:2] == ['django.db.utils.ProgrammingError', 'MySQLdb.ProgrammingError'], error
        assert error['errors'][0]['args'][0] == 1146 and 'w3_missing_migration_table' in error['errors'][0]['message'], observed
    assert observed['partial_schema_count'] == observed['partial_ddl'] == 1, observed
    assert observed['migrations'] == ['0001_initial','0002_status'] and observed['original_sentinel'] == [[17]], observed
    if runner=='pytest':
        assert observed['junit'] == dict(tests=2, failures=0, errors=2, skipped=0), observed
    else:
        assert not any(v['event']=='test_started' for v in values), observed
    return dict(result='PASS_FAILURE_DETECTED_BEFORE_TEST_BODY', baseline_captured=False, **observed)


def recipe(runner, broken, host, out):
    out.mkdir(parents=True)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(HERE), str(ROOT/'python'), str(out)]),
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', W3_RUN='1', W3_ORDER='normal',
               W3_RECIPE_RECEIPT=str(out/'owner.json'), W3_EVENTS=str(out/'events.jsonl'),
               W3_SUMMARY=str(out/'summary.json'), W3_BROKEN_MIGRATION=str(int(broken)))
    settings = 'example_settings'
    if broken:
        settings = 'recipe_failure_settings'
        (out/(settings+'.py')).write_text("from example_settings import *\nMIGRATION_MODULES={'orders':'failure_migrations'}\nTEST_RUNNER='observation.Runner'\n")
    argv = [sys.executable, str(HERE/'probe_recipe.py'), '--host', str(host),
            '--project', str(ROOT/'tests/e2e_native_control/pythonapp'), '--settings', settings,
            '--runner', runner, '--']
    if runner=='manage':
        argv += ['admission_cases.AdmissionCases' if broken else 'mixed_cases', '-v2']
    else:
        argv += ['-p','pytest_django.plugin','-p','order_probe',
                 str(HERE/('admission_cases.py' if broken else 'test_mixed_cases.py')), '-v', '--junitxml='+str(out/'pytest.xml')]
    result = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    (out/'stdout.txt').write_bytes(result.stdout)
    owner = json.loads((out/'owner.json').read_text())
    assert all(owner.values()) and result.returncode == int(broken), (owner, result.stdout.decode(errors='replace'))
    values = events(out)
    if broken:
        assert not any(v['event']=='test_body_admitted' for v in values)
        assert any(v['event']=='setup_failed' and v['errors'][0]['args'][0]==1146 for v in values)
    else:
        assert len([v for v in values if v['event']=='case_baseline']) == (6 if runner=='manage' else 12)
    return dict(result='PASS_RECIPE_ERROR_AND_CLEANUP' if broken else 'PASS_RECIPE', owner=owner, exit_code=result.returncode)
