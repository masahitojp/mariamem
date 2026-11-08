#!/usr/bin/env python3
"""Exact settings overlays and bounded observation of an existing C2 public stage.

Does not build a guest, translate/install a runtime, mutate the product, or claim
whole Issue129 acceptance. Runtime mode is reserved for the shared artifact wave.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import inspect_ref, require_commit

FIXTURES = {
    'internal/nativewire/c3_settings_observer.go': 'inspect.go.txt',
    'internal/live/c3_settings_observer.go': 'live_observer.go.txt',
    'c3_settings_test.go': 'public_settings_test.go.txt',
}
UNITS = {
    'internal/nativewire/c3_settings_observer_test.go': 'inspect_test.go.txt',
    'internal/live/c3_settings_observer_test.go': 'live_observer_test.go.txt',
}
TEST = 'TestNativePublicExactSettingsInheritance'
DURATIONS = ('1234567890', '30000000001')
PHASE_ROUTES = {('start', 'tcp'), ('start', 'pipe'), ('fork', 'tcp'),
                ('fork', 'pipe'), ('live', 'tcp'), ('reset', 'tcp')}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed5000(source):
    old = 'limit: limit,'
    if source.count(old) != 1:
        raise ValueError('inherited5000 control preimage changed')
    # Initial public Start remains exact; only restored Fork/Live instances
    # regress. This tests inheritance, rather than only detecting a bad default.
    new = ('limit: func() uint64 { if len(cfg.Restore) != 0 { '
           'return uint64(5000*time.Millisecond) }; return limit }(),')
    return source.replace(old, new, 1)


def overlay(product, directory, *, units=False, control=False):
    files = dict(FIXTURES)
    if units:
        files.pop('c3_settings_test.go')
        files.update(UNITS)
    replacements = {}
    for destination, fixture in files.items():
        target = product / destination
        if target.exists():
            raise ValueError('observer would shadow existing source: ' + destination)
        replacements[str(target)] = str(HERE / fixture)
    if control:
        target = product / 'internal/nativewire/backend.go'
        mutated = directory / 'backend.go'
        mutated.write_text(fixed5000(target.read_text()))
        replacements[str(target)] = str(mutated)
    path = directory / 'overlay.json'
    path.write_text(json.dumps({'Replace': replacements}, indent=2) + '\n')
    return path


def observations(log, duration):
    if not re.search(r'^--- PASS: ' + TEST + r' \(', log, re.M) or '--- SKIP:' in log:
        raise ValueError('settings fixture did not complete')
    rows = [json.loads(line.split('C3_SETTINGS ', 1)[1])
            for line in log.splitlines() if 'C3_SETTINGS ' in line]
    if len(rows) != 6 or {(r['phase'], r['route']) for r in rows} != PHASE_ROUTES:
        raise ValueError('incomplete/duplicate settings observation census')
    epochs = {}
    for row in rows:
        if (row['case'] != TEST + '/' + duration or row['timeout_ns'] != duration
                or row['startup_ns'] != '90000000017' or row['shutdown_ns'] != '20000000019'
                or row['live_generation'] != (1 if row['phase'] == 'reset' else 0)
                or type(row['epoch']) is not int or row['epoch'] <= 0
                or type(row['generation']) is not int or row['generation'] <= 0
                or type(row['slot']) is not int or not 0 <= row['slot'] < 16):
            raise ValueError('incorrect settings observation')
        epochs.setdefault(row['phase'], set()).add(row['epoch'])
    if any(len(v) != 1 for v in epochs.values()) or len(set().union(*epochs.values())) != 4:
        raise ValueError('lifecycle phases did not reach distinct runtime epochs')
    return rows


def control_detected(result, duration):
    # Compile/timeout/unrelated failures and host-only option checks cannot pass.
    marker = f'exact guest timeout phase=fork route=tcp: got 5000000000 want {duration}'
    starts = [json.loads(line.split('C3_SETTINGS ', 1)[1])
              for line in result.stdout.splitlines() if 'C3_SETTINGS ' in line]
    return (result.returncode != 0 and marker in result.stdout
            and '--- FAIL: ' + TEST in result.stdout
            and '[build failed]' not in result.stdout and 'panic:' not in result.stdout
            and len(starts) == 2
            and {(r['phase'], r['route']) for r in starts} == {('start', 'tcp'), ('start', 'pipe')}
            and all(r['timeout_ns'] == duration for r in starts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('unit', 'runtime'), required=True)
    parser.add_argument('--workspace', type=Path, help='existing C2 public staging workspace')
    parser.add_argument('--expected-host-source-commit')
    parser.add_argument('--expected-guest-sha256')
    parser.add_argument('--evidence', type=Path, required=True, help='fresh owned output directory')
    args = parser.parse_args()
    identity = inspect_ref(ROOT, 'HEAD')
    require_commit(ROOT, identity.source_commit)
    evidence = args.evidence.resolve()
    if evidence.is_relative_to(ROOT):
        raise ValueError("evidence must be outside the source checkout")
    evidence.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, GOTOOLCHAIN='go1.26.10', CGO_ENABLED='1',
               GOMAXPROCS='2', GOWORK='off', GOFLAGS='')

    def run(command, name, cwd):
        result = subprocess.run([str(x) for x in command], cwd=cwd, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
        (evidence / (name + '.txt')).write_text(result.stdout)
        return result

    fixtures = {name: digest(HERE / name) for name in set(FIXTURES.values()) | set(UNITS.values())}
    if args.mode == 'unit':
        with tempfile.TemporaryDirectory(prefix='settings-unit-') as temporary:
            control = overlay(ROOT, Path(temporary), units=True)
            result = run(['go', 'test', '-race', '-overlay=' + str(control),
                          './internal/nativewire', './internal/live', '-run', '^TestC3',
                          '-count=1', '-timeout=30s'], 'unit-race', ROOT)
            if result.returncode:
                raise RuntimeError(result.stdout)
        report = dict(result='PASS observer unit/race only', source_commit=identity.source_commit,
                      fixtures_sha256=fixtures, runtime_acceptance='UNEXECUTED')
    else:
        if not args.workspace or not args.expected_host_source_commit or not re.fullmatch('[0-9a-f]{64}', args.expected_guest_sha256 or ''):
            parser.error('runtime mode requires workspace and exact expected host/guest identities')
        require_commit(ROOT, args.expected_host_source_commit)
        from dev_guest import inventory, source_identity
        observer = source_identity(ROOT)  # fail before build on uncommitted fixtures
        w = args.workspace.resolve()
        product = w / 'temp/public/product'
        receipt_path = w / 'evidence/public-source.json'
        receipt = json.loads(receipt_path.read_text())
        if (receipt['host_source_commit'] != args.expected_host_source_commit
                or receipt['guest_sha256'] != args.expected_guest_sha256
                or receipt['source_inventory'] != inventory(product)):
            raise ValueError('public artifact identity/inventory differs')
        if 'StartNative(' not in (product / 'internal/host/factory.go').read_text() or 'panic("legacy wire route tripwire")' not in (product / 'internal/mysqlwire/wire.go').read_text():
            raise ValueError('expected native factory and legacy tripwire')
        env['CGO_ENABLED'] = '0'
        env['GOCACHE'] = str(w / 'temp/gocache')
        env['GOMODCACHE'] = str(w / 'temp/gomodcache')
        rows, controls = [], []
        with tempfile.TemporaryDirectory(dir=w / 'temp', prefix='settings-') as temporary:
            temp = Path(temporary)
            binary = temp / 'settings.test'
            positive = overlay(product, temp)
            result = run(['go', 'test', '-c', '-p', '1', '-trimpath', '-buildvcs=false',
                          '-overlay=' + str(positive), '-o', binary, '.'], 'compile', product)
            if result.returncode:
                raise RuntimeError(result.stdout)
            positive_sha = digest(binary)
            for duration in DURATIONS:
                result = run([binary, '-test.v', '-test.run=^' + TEST + '/' + duration + '$',
                              '-test.timeout=180s'], 'positive-' + duration, product)
                if result.returncode:
                    raise RuntimeError(result.stdout)
                rows.extend(observations(result.stdout, duration))
            negative = overlay(product, temp, control=True)
            mutation_sha = digest(temp / 'backend.go')
            result = run(['go', 'test', '-c', '-p', '1', '-trimpath', '-buildvcs=false',
                          '-overlay=' + str(negative), '-o', binary, '.'], 'control-compile', product)
            if result.returncode:
                raise RuntimeError(result.stdout)
            negative_sha = digest(binary)
            for duration in DURATIONS:
                result = run([binary, '-test.v', '-test.run=^' + TEST + '/' + duration + '$',
                              '-test.timeout=180s'], 'inherited5000-' + duration, product)
                if not control_detected(result, duration):
                    raise RuntimeError('5000ms control not detected by exact guest assertion:\n' + result.stdout)
                controls.append(dict(duration_ns=duration, detected=True, exit=result.returncode))
        if inventory(product) != receipt['source_inventory'] or source_identity(ROOT) != observer:
            raise ValueError('observation changed source')
        report = dict(result='PASS bounded Go public exact inheritance',
                      observer_source_commit=identity.source_commit,
                      host_source_commit=receipt['host_source_commit'], guest_sha256=receipt['guest_sha256'],
                      platform=sys.platform, fixtures_sha256=fixtures,
                      source_receipt_sha256=digest(receipt_path), observations=rows, controls=controls,
                      positive_binary_sha256=positive_sha, control_binary_sha256=negative_sha,
                      control_source_sha256=mutation_sha,
                      not_verified=['installed Python shared/control exact settings', 'original full C3 lifecycle/fault oracles',
                                    'opposite native OS', 'Issue129 whole acceptance', 'adoption', 'release'])
    report['observer_sha256'] = digest(Path(__file__))
    (evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
