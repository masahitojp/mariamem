#!/usr/bin/env python3
"""G1 physical ownership controls, semantic mutations and external module consumer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import tempfile
import time

from consumer_module import MODULE, prepare_proxy, source_identity
from consumer_acceptance import verify_module_files
from git_identity import require_commit

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ('mariamem_test.go', 'mariamemtest/physical_test.go', 'mariamemtest/fixture_test.go',
          'scripts/go_fixture_completion.py', 'scripts/consumer_module.py',
          'scripts/consumer_acceptance.py', 'tests/fixture_entry_acceptance/consumer_test.go.txt')
ROOT_CASES = ('preserved', 'consumed', 'success', 'backing-close-error', 'invalid', 'source-close-error')
HELPER_CASES = ('preserved', 'consumed', 'partial-baseline', 'invalid', 'cleanup-error')
EXTERNAL_CASES = ('TestFirstCommit', 'TestSecondSeed', 'TestParallel',
                  'TestOrdinaryFailureDoesNotContaminate', 'TestMigrationFailure', 'TestCancelledPrepare')
# Overlays modify only these exact handwritten boundaries, never the checkout.
# Each mutation must run its named test and fail semantically, not just fail to build.
MUTATIONS = {
    'skip-source-close': ('mariamemtest/fixture.go', 'sourceErr := source.Close()', 'sourceErr := error(nil)',
                          './mariamemtest', 'TestFixturePhysicalCleanup/preserved', 'source owner'),
    'skip-baseline-close': ('mariamemtest/fixture.go', 'cleanup = errors.Join(cleanup, base.Close())',
                            'cleanup = errors.Join(cleanup, error(nil))', './mariamemtest',
                            'TestFixturePhysicalCleanup/partial-baseline', 'partial baseline'),
    'double-consumed-teardown': ('mariamem.go', 'if db.closed {\n\t\treturn db.closeErr',
                                 'if db.closed && db.server == nil {\n\t\treturn db.closeErr', '.',
                                 'TestSnapshotPhysicalOwnership/success', 'backend teardown'),
    'skip-backing-release': ('snapshot.go', 'hostError(errors.Join(e, backing.Close()), "snapshot_failed", consumed)',
                             'hostError(e, "snapshot_failed", consumed)', '.',
                             'TestSnapshotPhysicalOwnership/consumed', 'partial backing descriptor retained'),
    'leak-permit': ('mariamemtest/fixture.go', '<-f.permits', '_ = c.permit', './mariamemtest',
                    'TestBoundedAdmissionAndCancellation', 'deadline exceeded'),
    'bypass-cap': ('mariamemtest/fixture.go', 'make(chan struct{}, opts.MaxForks)',
                   'make(chan struct{}, opts.MaxForks+1)', './mariamemtest',
                   'TestBoundedAdmissionAndCancellation', 'fixture_test.go'),
    'drop-original-error': ('mariamemtest/fixture.go', 'Err: cause, CleanupErr: cleanup',
                            'Err: nil, CleanupErr: cleanup', './mariamemtest',
                            'TestSetupFailuresKeepCauseAndCleanup/prepare', 'fixture_test.go'),
    'drop-cleanup-error': ('mariamemtest/fixture.go', 'Err: cause, CleanupErr: cleanup',
                           'Err: cause, CleanupErr: nil', './mariamemtest',
                           'TestSetupFailuresKeepCauseAndCleanup/prepare', 'fixture_test.go'),
}


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def events(text):
    return [json.loads(line) for line in text.splitlines() if line.startswith('{')]


def semantic_failure(text, target, marker, code):
    need(code == 1 and any(e.get('Action') == 'fail' and e.get('Test') == target for e in events(text))
         and marker in text, 'mutation was not detected by its semantic oracle: ' + target)


def mutate(text, before, after):
    need(text.count(before) == 1, 'mutation anchor changed; do not silently skip a control')
    return text.replace(before, after, 1)


def baseline_cases():
    return ({'TestSnapshotPhysicalOwnership/' + c for c in ROOT_CASES}
            | {'TestFixturePhysicalCleanup/' + c for c in HELPER_CASES}
            | {'TestCaptureFailureDoesNotClaimInternalCleanupKnown'}
            | {row[4] for row in MUTATIONS.values()})


def command(argv, cwd, log, env=None, timeout=600, expected=0):
    start = time.monotonic()
    with Path(log).open('w') as stream:
        proc = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try: os.killpg(proc.pid, sig)
                except ProcessLookupError: pass
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired: continue
            raise ValueError('command timeout; process-group termination attempted, cleanup requires inspection: ' + Path(log).name)
    if expected is not None:
        need(code == expected, 'command failed: ' + Path(log).name)
    return code, time.monotonic() - start


def verify_resolved(record, tag, root=ROOT):
    need(record.get('Path') == MODULE and record.get('Version') == tag and 'Replace' not in record,
         'wrong/replaced consumer module')
    directory = Path(record['Dir']).resolve()
    need(not directory.is_relative_to(root.resolve()), 'consumer library came from repository')
    return verify_module_files(record, root)


def consumer_result(text):
    summary = json.loads(text.splitlines()[-1])
    need(summary == {'result': 'PASS_EXTERNAL_FIXTURE', 'prepares': 1}, 'external fixture setup/exit failed')
    need(all('--- PASS: ' + name + ' ' in text for name in EXTERNAL_CASES), 'external case census incomplete')
    return summary


def fault_controls(output):
    positive = output / 'physical.jsonl.txt'
    command(['go', 'test', '-p', '1', '-json', '.', './mariamemtest', '-count=1', '-timeout=60s',
             '-run', '^Test(SnapshotPhysicalOwnership|FixturePhysicalCleanup|CaptureFailureDoesNotClaimInternalCleanupKnown|BoundedAdmissionAndCancellation|SetupFailuresKeepCauseAndCleanup)$'],
            ROOT, positive)
    passed = {e.get('Test') for e in events(positive.read_text()) if e.get('Action') == 'pass'}
    expected = baseline_cases()
    need(expected <= passed, 'physical fault census incomplete')
    results = []
    overlays = output / 'overlays'
    overlays.mkdir()
    for name, (path, before, after, package, target, marker) in MUTATIONS.items():
        variant = overlays / (name + '.go')
        variant.write_text(mutate((ROOT / path).read_text(), before, after))
        config = overlays / (name + '.json')
        write(config, {'Replace': {str(ROOT / path): str(variant)}})
        log = output / (name + '.jsonl.txt')
        selector = '/'.join('^' + re.escape(part) + '$' for part in target.split('/'))
        code, elapsed = command(['go', 'test', '-p', '1', '-json', '-overlay', config, package,
                                 '-run', selector, '-count=1', '-timeout=15s'], ROOT, log, expected=None)
        semantic_failure(log.read_text(), target, marker, code)
        results.append({'mutation': name, 'result': 'DETECTED', 'target': target,
                        'exit_code': code, 'overlay_sha256': digest(variant), 'elapsed_seconds': elapsed})
    return {'result': 'PASS', 'physical_cases': sorted(expected), 'mutations': results}


def external_consumer(output):
    # A source-content version makes cache reuse stable across record-only commits.
    # This is a private proxy fixture, never a public release/tag or qualification.
    tag = 'v0.0.0-g1.' + source_identity(ROOT)[:16]
    with tempfile.TemporaryDirectory(prefix='mariamem-g1-external-') as temporary:
        work = Path(temporary).resolve()
        need(not work.is_relative_to(ROOT), 'consumer must be outside repository')
        proxy = prepare_proxy(ROOT, work, tag)
        project = work / 'consumer'; project.mkdir()
        shutil.copyfile(ROOT / 'tests/fixture_entry_acceptance/consumer_test.go.txt', project / 'fixture_test.go')
        (project / 'go.mod').write_text('module example.com/g1-consumer\n\ngo 1.26.0\n\nrequire ' + MODULE + ' ' + tag + '\n')
        shutil.copyfile(ROOT / 'go.sum', project / 'go.sum')
        sdk = subprocess.check_output(['go', 'env', 'GOROOT'], text=True).strip()
        compiler = str(Path(sdk) / 'bin/go')
        env = {k: v for k, v in os.environ.items() if k not in ('GH_TOKEN', 'GITHUB_TOKEN')
               and not k.startswith(('GO', 'MARIAMEM_', 'MYSQLMEM_', 'PYTHON', 'PYTEST_'))}
        env.update(GOWORK='off', GOENV='off', GOTOOLCHAIN='local', GOFLAGS='-p=1 -trimpath', CGO_ENABLED='0',
                   GOPROXY=proxy.as_uri() + ',https://proxy.golang.org', GONOSUMDB=MODULE, GOSUMDB='sum.golang.org')
        version = subprocess.check_output([compiler, 'version'], env=env, text=True).split()[2]
        need(version == 'go1.26.10', 'external compiler must be Go1.26.10')
        runtime_tmp = work / 'runtime-tmp'; runtime_tmp.mkdir(); env['TMPDIR'] = str(runtime_tmp)
        command([compiler, 'mod', 'download', MODULE + '@' + tag], project, output / 'module-download.txt',
                {**env, 'GOPROXY': proxy.as_uri()})
        command([compiler, 'mod', 'tidy'], project, output / 'module-tidy.txt', env)
        resolved = json.loads(subprocess.check_output([compiler, 'list', '-m', '-json', MODULE], cwd=project, env=env, text=True))
        inventory = verify_resolved(resolved, tag)
        need(subprocess.check_output([compiler, 'env', 'GOMOD'], cwd=project, env=env, text=True).strip()
             == str(project / 'go.mod'), 'consumer used another module/workspace')
        binary = work / 'consumer.test'
        command([compiler, 'test', '-c', '-o', binary], project, output / 'consumer-build.txt', env)
        runs = []
        for mode in ('normal', 'shuffle'):
            log = output / ('consumer-' + mode + '.txt')
            argv = [binary, '-test.v', '-test.parallel=4', '-test.timeout=3m']
            if mode == 'shuffle': argv.append('-test.shuffle=on')
            _, elapsed = command(argv, project, log, {**env, 'GOPROXY': 'off'}, timeout=240)
            text = log.read_text()
            consumer_result(text)
            runs.append({'mode': mode, 'result': 'PASS', 'elapsed_seconds': elapsed, 'cases': list(EXTERNAL_CASES)})
        need(not list(runtime_tmp.iterdir()), 'external consumer temporary owners remain')
        return {'result': 'PASS', 'module_path': MODULE, 'private_module_version': tag,
                'module_files': inventory, 'module_sum': resolved['Sum'],
                'replace': False, 'outside_repository': True, 'GOWORK': 'off', 'GOTOOLCHAIN': 'local',
                'toolchain': version, 'cache_state': 'existing Go compiler/module caches; not cold qualification',
                'binary_sha256': digest(binary), 'runs': runs, 'temporary_cleanup': 'complete'}


def validate(directory, expected):
    directory = Path(directory)
    data = json.loads((directory / 'result.json').read_text())
    need(data['result'] == 'PASS' and data['source_commit'] == expected, 'completion source/result mismatch')
    need(data['toolchain'] == 'go1.26.10', 'fault-control compiler mismatch')
    need(data['source_inventory_sha256'] == source_identity(ROOT), 'completion production bytes differ')
    need(data['inputs_sha256'] == {p: digest(ROOT / p) for p in INPUTS}, 'completion harness bytes differ')
    fault = data['faults']
    positive_events = events((directory / 'physical.jsonl.txt').read_text())
    need(set(fault['physical_cases']) == baseline_cases()
         and baseline_cases() <= {e.get('Test') for e in positive_events if e.get('Action') == 'pass'}
         and not any(e.get('Action') == 'fail' for e in positive_events), 'positive fault census missing/failed')
    need(fault['result'] == 'PASS' and {m['mutation'] for m in fault['mutations']} == set(MUTATIONS)
         and len(fault['mutations']) == len(MUTATIONS)
         and all(m['result'] == 'DETECTED' for m in fault['mutations']), 'fault/mutation census incomplete')
    for m in fault['mutations']:
        path, before, after, _, target, marker = MUTATIONS[m['mutation']]
        need(m['target'] == target and m['overlay_sha256'] == hashlib.sha256(mutate((ROOT / path).read_text(), before, after).encode()).hexdigest(), 'mutation target/overlay drift')
        semantic_failure((directory / (m['mutation'] + '.jsonl.txt')).read_text(), target, marker, m['exit_code'])
    consumer = data['consumer']
    need(consumer['result'] == 'PASS' and not consumer['replace'] and consumer['outside_repository']
         and consumer['temporary_cleanup'] == 'complete', 'consumer isolation/cleanup incomplete')
    need(consumer['toolchain'] == 'go1.26.10' and consumer['GOWORK'] == 'off'
         and consumer['GOTOOLCHAIN'] == 'local', 'consumer toolchain/workspace mismatch')
    need(consumer['module_path'] == MODULE
         and consumer['private_module_version'] == 'v0.0.0-g1.' + source_identity(ROOT)[:16]
         and consumer['module_sum'].startswith('h1:'), 'consumer module identity incomplete')
    need(consumer['module_files'] == {p.relative_to(ROOT).as_posix(): digest(p)
         for p in __import__('consumer_module').source_files(ROOT)}, 'consumer source inventory mismatch')
    need({r['mode'] for r in consumer['runs']} == {'normal', 'shuffle'} and len(consumer['runs']) == 2
         and all(r['result'] == 'PASS' and set(r['cases']) == set(EXTERNAL_CASES) for r in consumer['runs']), 'consumer cases missing')
    for mode in ('normal', 'shuffle'):
        consumer_result((directory / ('consumer-' + mode + '.txt')).read_text())
    sums = json.loads((directory / 'SHA256SUMS.json').read_text())
    required = {'result.json', 'physical.jsonl.txt', 'consumer-normal.txt', 'consumer-shuffle.txt'}
    required |= {name + '.jsonl.txt' for name in MUTATIONS}
    need(required <= sums.keys(), 'completion receipt files missing')
    for name, sha in sums.items():
        path = Path(name)
        need(not path.is_absolute() and '..' not in path.parts and digest(directory / path) == sha, 'completion checksum mismatch')
    return data


def run(expected, output):
    require_commit(ROOT, expected)
    need(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == expected
         and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT), 'completion requires exact clean source')
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    toolchain = subprocess.check_output(['go', 'version'], text=True).split()[2]
    need(toolchain == 'go1.26.10', 'requires Go1.26.10 before fault controls')
    data = {'result': 'RUNNING', 'source_commit': expected, 'source_inventory_sha256': source_identity(ROOT),
            'toolchain': toolchain,
            'inputs_sha256': {p: digest(ROOT / p) for p in INPUTS},
            'ci': {k: os.getenv(k) for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_JOB')}}
    try:
        data['faults'] = fault_controls(output)
        data['consumer'] = external_consumer(output)
        need(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT), 'source became dirty')
        data['result'] = 'PASS'
    except Exception as exc:
        data.update(result='FAIL', error=str(exc)); raise
    finally:
        write(output / 'result.json', data)
        write(output / 'SHA256SUMS.json', {p.relative_to(output).as_posix(): digest(p) for p in output.rglob('*')
              if p.is_file() and p.suffix in ('.json', '.txt') and p.name != 'SHA256SUMS.json'})
    validate(output, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--validate-matrix', type=Path)
    args = parser.parse_args()
    if args.validate_matrix:
        for host in ('macos-15', 'ubuntu-24.04'):
            validate(args.validate_matrix / ('go-fixture-host-' + host + '-' + args.expected_source_commit) / 'completion', args.expected_source_commit)
        print('G1_FAULT_AND_EXTERNAL_CONSUMER_MATRIX_PASS')
    else:
        need(args.output is not None, '--output required')
        run(args.expected_source_commit, args.output)
        print('G1_FAULT_AND_EXTERNAL_CONSUMER_PASS')


if __name__ == '__main__':
    main()
