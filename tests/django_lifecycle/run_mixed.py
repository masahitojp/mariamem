"""Mixed-order comparison, partial migration failure and runnable recipe checks."""
import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-port', required=True, type=int)
    parser.add_argument('--host', required=True, type=Path)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE/'input-manifest.json').read_text())
    for name, digest in manifest['application_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
    for name, version in manifest['versions'].items():
        assert importlib.metadata.version(name) == version, name
    base.verify_go_binary(ROOT, args.host.resolve(), args.expected_source_commit)
    output = args.output.resolve();output.mkdir(parents=True, exist_ok=False)
    token = 'w3mix_' + uuid.uuid4().hex[:10];original, target = token, 'test_'+token
    native = dict(host='127.0.0.1',port=args.native_port)
    assert base.query(native,'SELECT VERSION()')[0][0].startswith('12.3.3-MariaDB')
    report = dict(source_commit=args.expected_source_commit, python=sys.version, routes={}, failure_routes={}, recipes={})
    keys = [(r,o) for r in ('manage','pytest') for o in ORDERS]
    try:
        base.initialize(native, original)
        refs = [mixed(native, original, target, r,o,output/'native'/(r+'-'+o)) for r,o in keys]
        report['routes']['native'] = refs
        import mariamem
        source = mariamem.start(host_binary=args.host.resolve());session=source._session
        try:
            info=source.connection_info();base.initialize(info, original)
            report['routes']['guest-standard']=[mixed(info, original,target,r,o,output/'guest-standard'/(r+'-'+o),reference=refs[i]) for i,(r,o) in enumerate(keys)]
            preparation=subprocess.run([sys.executable,str(HERE/'prepare.py')],env=base.environment(info,original,target,output,'prepare'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            (output/'preparation.txt').write_bytes(preparation.stdout);assert preparation.returncode==0
            source.wait_disconnected()
            with source.snapshot() as saved:
                report['source_consumed']=source.closed
                for copy in (1,2):
                    runs=[]
                    for i,(r,o) in enumerate(keys):
                        with saved.fork() as child:
                            runs.append(mixed(child.connection_info(),original,target,r,o,output/f'fork-{copy}'/(r+'-'+o),reuse=True,reference=refs[i]))
                    report['routes'][f'fork-{copy}']=runs
        finally:
            source.close();report['guest_owner_cleanup']=dict(reaped=session._process.poll() is not None,temp_removed=not session.root.exists())
        assert all(report['guest_owner_cleanup'].values()) and report['source_consumed']
        # Destructive migration checks always use fresh owners; no failed source
        # is admitted to a Snapshot, another test or the following recipe run.
        for runner in ('manage','pytest'):
            try:
                report['failure_routes']['native-'+runner]=failure(native,original,target,runner,output/'migration-failure'/('native-'+runner))
            finally:
                base.query(native,f'DROP DATABASE IF EXISTS `{target}`')
            source=mariamem.start(host_binary=args.host.resolve());session=source._session
            try:
                info=source.connection_info();base.initialize(info,original)
                observed=failure(info,original,target,runner,output/'migration-failure'/('guest-'+runner))
            finally:
                source.close()
            observed['owner_cleanup']=dict(reaped=session._process.poll() is not None,temp_removed=not session.root.exists())
            assert all(observed['owner_cleanup'].values())
            report['failure_routes']['guest-'+runner]=observed
        for runner in ('manage','pytest'):
            for broken in (False,True):
                name=runner+('-failure' if broken else '-normal')
                report['recipes'][name]=recipe(runner,broken,args.host.resolve(),output/'recipe'/name)
        report['result']='PASS_LOCAL_DJANGO_MIXED_AND_FAILURE'
    finally:
        base.query(native,f'DROP DATABASE IF EXISTS `{target}`');base.query(native,f'DROP DATABASE IF EXISTS `{original}`')
        report['native_schemas_removed']=base.schemas(native,target)==base.schemas(native,original)==0
        base.write(output/'result.json',report)
    assert report['native_schemas_removed']
    print(json.dumps(dict(result=report['result'],python=sys.version.split()[0],mixed_suites=32,migration_failure_suites=4,recipe_runs=4)))


if __name__=='__main__':
    main()
