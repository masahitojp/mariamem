#!/usr/bin/env python3
"""Accept exact packaged FAST artifacts; no builds, publication, or local fallback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from native_target import DARWIN, UBUNTU
from platform_acceptance import MODULE, bind_remote_origin, check_artifacts, digest, extract, isolated_env
from prepared_auth_keys import key_material

ROOT = Path(__file__).resolve().parents[1]


def clean_env(work):
    prefixes = ('MARIAMEM_', 'MYSQLMEM_', 'WASMER_', 'WASIX_', 'PYTHON', 'PYTEST',
                'PIP_', 'GO', 'DYLD_', 'LD_', 'GIT_')
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(prefixes) and k not in ('VIRTUAL_ENV', 'GH_TOKEN', 'GITHUB_TOKEN')}
    temporary = work / 'runtime-tmp'
    temporary.mkdir()
    env.update(TMPDIR=str(temporary), PYTHONNOUSERSITE='1',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    return env


def verify_inputs(native, wheel, target):
    """Bind shared guest/runtime bytes; the Go archive intentionally omits host."""
    checked = check_artifacts(native, target)
    manifest = json.loads((native / 'manifest.json').read_text())
    files = manifest['sha256']
    with zipfile.ZipFile(wheel) as archive:
        def contents(name):
            suffix = 'mariamem/_native/' + name
            matches = [n for n in archive.namelist() if n == suffix or n.endswith('/' + suffix)]
            if len(matches) != 1:
                raise ValueError('missing/duplicate wheel native file: ' + name)
            return archive.read(matches[0])
        wheel_manifest = json.loads(contents('manifest.json'))
        common = lambda m: {k: v for k, v in m.items() if k not in ('sha256', 'public_release_ready')}
        if common(wheel_manifest) != common(manifest):
            raise ValueError('wheel/archive native compatibility metadata differs')
        wheel_files = wheel_manifest['sha256']
        if not {'mariamem-host', *files}.issubset(wheel_files):
            raise ValueError('wheel manifest lacks required native artifacts')
        for name, value in wheel_files.items():
            if Path(name).name != name:
                raise ValueError('unsafe native manifest filename')
            data = contents(name)
            if hashlib.sha256(data).hexdigest() != value:
                raise ValueError('wheel native hash mismatch: ' + name)
            if name in files:
                path = native / name
                if not path.is_file() or path.is_symlink() or data != path.read_bytes():
                    raise ValueError('wheel/archive native bytes differ: ' + name)
    if not os.access(native / 'wasmer-headless', os.X_OK):
        raise ValueError('native executable permission missing: wasmer-headless')
    return {**checked, 'wheel_manifest': wheel_manifest, 'shared_native_bytes_match': True}


def verify_guest_check(mode, code, stdout, stderr):
    if mode == 'valid':
        if code:
            raise ValueError('valid prepared-key guest exited unsuccessfully')
        result = json.loads(stdout)
        if (result.get('prepared_auth_keys') != 'PASS' or result.get('generated') is not False
                or result.get('actual_callback') is not True):
            raise ValueError('missing actual callback/no-generation evidence')
        return result
    if code == 0 or '"prepared_auth_keys":"PASS"' in stdout:
        raise ValueError('invalid prepared key was accepted')
    if 'mariamem:' not in stderr or 'RSA' not in stderr or 'matching native bundle' not in stderr:
        raise ValueError('key failure lacks actionable guest diagnostic')
    return {'rejected': True, 'actionable_guest_diagnostic': True}


INSTALLED_CHECK = '''import hashlib, json
from pathlib import Path
import mariamem, pymysql
expected = json.loads(Path('expected.json').read_text())
package = Path(mariamem.__file__).resolve().parent
assert package.is_relative_to(Path('venv').resolve()), str(package)
native = package / '_native'
assert json.loads((native / 'manifest.json').read_text()) == expected['manifest']
for name, value in expected['manifest']['sha256'].items():
    assert hashlib.sha256((native / name).read_bytes()).hexdigest() == value, name
with mariamem.start() as db:
    with pymysql.connect(**db.connection_info()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT PLUGIN_STATUS FROM information_schema.PLUGINS WHERE PLUGIN_NAME='caching_sha2_password'")
            assert cursor.fetchall() == (('ACTIVE',),)
            cursor.execute("SHOW STATUS LIKE 'Caching_sha2_password_rsa_public_key'")
            row = cursor.fetchone()
            assert row and row[1] == expected['public_key'], row
    db.wait_disconnected()
print(json.dumps({'passed': True, 'installed_native_matches_archive': True,
                  'plugin_active': True, 'public_key_matches_fixture': True,
                  'public_key_sha256': hashlib.sha256(expected['public_key'].encode()).hexdigest()}))
'''

GO_KEY_CHECK = r'''package main

import (
    "context"
    "database/sql"
    "os"
    "testing"
    "time"
    "github.com/masahitojp/mariamem"
)

func TestPreparedAuthenticationKey(t *testing.T) {
    ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
    defer cancel()
    db, err := mariamem.Start(ctx, mariamem.Options{NativeDir: os.Getenv("FAST_TRANCHE_NATIVE")})
    if err != nil { t.Fatal(err) }
    defer func() { if err := db.Close(); err != nil { t.Error(err) } }()
    pool, err := sql.Open("mysql", db.DSN())
    if err != nil { t.Fatal(err) }
    defer pool.Close()
    var status string
    err = pool.QueryRowContext(ctx, "SELECT PLUGIN_STATUS FROM information_schema.PLUGINS WHERE PLUGIN_NAME='caching_sha2_password'").Scan(&status)
    if err != nil || status != "ACTIVE" { t.Fatalf("plugin status %q: %v", status, err) }
    var name, key string
    err = pool.QueryRowContext(ctx, "SHOW STATUS LIKE 'Caching_sha2_password_rsa_public_key'").Scan(&name, &key)
    if err != nil { t.Fatal(err) }
    expected, err := os.ReadFile("expected-public.pem")
    if err != nil || key != string(expected) { t.Fatalf("public key mismatch: %v", err) }
    if err := pool.Close(); err != nil { t.Fatal(err) }
    if err := db.WaitDisconnected(ctx); err != nil { t.Fatal(err) }
}
'''


def run(args):
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'result': 'FAIL', 'target': args.target,
              'source_sha': args.source_sha, 'steps': {},
              'coverage': {'rsa_failure': 'direct packaged guest CLI; public APIs have no key fault-injection option',
                           'public_diagnostics': 'Go missing-native; installed-wheel artifact mismatch and runtime startup regression',
                           'auth': 'real guest callback acceptance; ordinary SQL retains grant bypass'}}
    report_path = evidence / 'acceptance.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')

    def execute(name, argv, cwd, env, timeout=900, expected=0):
        report['steps'][name] = {'status': 'RUNNING', 'argv': [str(x) for x in argv]}
        save()
        try:
            result = subprocess.run([str(x) for x in argv], cwd=cwd, env=env,
                                    capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            for stream in ('stdout', 'stderr'):
                value = getattr(exc, stream) or b''
                (evidence / (name + '.' + stream)).write_bytes(value.encode() if isinstance(value, str) else value)
            report['steps'][name].update(status='FAIL', timeout_seconds=timeout)
            save()
            raise
        (evidence / (name + '.stdout')).write_text(result.stdout)
        (evidence / (name + '.stderr')).write_text(result.stderr)
        report['steps'][name].update(exit_code=result.returncode,
                                    status='PASS' if expected is None or result.returncode == expected else 'FAIL')
        save()
        if expected is not None and result.returncode != expected:
            raise RuntimeError(name + ' failed; inspect saved stdout/stderr')
        return result

    save()
    try:
        for name, path, expected in (('native_archive', args.native_archive, args.native_sha256),
                                     ('wheel', args.wheel, args.wheel_sha256)):
            actual = digest(path)
            report[name] = {'filename': path.name, 'sha256': actual, 'expected_sha256': expected}
            if actual != expected:
                raise ValueError(name + ' SHA256 mismatch')
        with tempfile.TemporaryDirectory(prefix='mariamem-fast-acceptance-', dir='/tmp') as directory:
            work = Path(directory).resolve()
            env = clean_env(work)
            commit = execute('source_identity', ['git', '-C', ROOT, 'rev-parse', 'HEAD'], work, env).stdout.strip()
            if commit != args.source_sha:
                raise ValueError('acceptance checkout differs from expected source SHA')
            harness_files = ['scripts/fast_tranche_acceptance.py', 'scripts/platform_acceptance.py',
                             'scripts/platform_acceptance/consumer.go', 'scripts/prepared_auth_keys.py',
                             'scripts/ubuntu_acceptance/lifecycle.go',
                             'scripts/native_target.py', 'guest/test-auth-keypair.json',
                             'tests/verify_alpha.py', 'tests/consumer/test_database.py',
                             'tests/consumer/test_ubuntu.py']
            execute('harness_source_clean', ['git', '-C', ROOT, 'diff', '--exit-code',
                    args.source_sha, '--', *harness_files], work, env)
            report['harness_sha256'] = {name: digest(ROOT / name) for name in harness_files}
            native = extract(args.native_archive, work / 'native', args.target)
            report['artifacts'] = verify_inputs(native, args.wheel, args.target)
            save()
            execute('go_public_consumer', [args.python, ROOT / 'scripts/platform_acceptance.py',
                    '--target', args.target, '--archive', args.native_archive,
                    '--sha256', args.native_sha256, '--module', args.source_sha,
                    '--expected-commit', args.source_sha, '--go', args.go,
                    '--evidence', evidence / 'go-public.json'], work, env, timeout=1800)
            go = json.loads((evidence / 'go-public.json').read_text())
            if go.get('platform_acceptance_passed') is not True:
                raise ValueError('public Go acceptance lacks PASS')
            report['go_public_acceptance'] = go
            # Additional timeout/key checks share a second external module pinned
            # to the same independently verified public commit, never a replace.
            go_state = work / 'go-state'
            go_state.mkdir()
            go_env = isolated_env(go_state)
            go_env = {**env, **{k: v for k, v in go_env.items() if k.startswith('GO') or k in ('TMPDIR', 'CGO_ENABLED')},
                      'FAST_TRANCHE_NATIVE': str(native)}
            go_consumer = work / 'go-consumer'
            go_consumer.mkdir()
            shutil.copy2(ROOT / 'scripts/ubuntu_acceptance/lifecycle.go', go_consumer / 'main.go')
            (go_consumer / 'keys_test.go').write_text(GO_KEY_CHECK)
            (go_consumer / 'expected-public.pem').write_text(key_material()['public'])
            execute('go_lifecycle_module', [args.go, 'mod', 'init', 'example.com/mariamem-fast-acceptance'], go_consumer, go_env)
            execute('go_lifecycle_fetch', [args.go, 'get', MODULE + '@' + args.source_sha,
                    'github.com/go-sql-driver/mysql@v1.9.3'], go_consumer, go_env)
            resolved = json.loads(execute('go_lifecycle_resolved', [args.go, 'list', '-m', '-json', MODULE],
                                         go_consumer, go_env).stdout)
            if resolved.get('Replace'):
                raise ValueError('external Go consumer forbids local replacement')
            remote = json.loads(execute('go_lifecycle_origin', [args.go, 'list', '-m', '-json', MODULE + '@' + args.source_sha],
                                       go_consumer, {**go_env, 'GOPROXY': 'direct'}).stdout)
            report['go_lifecycle_module'] = bind_remote_origin(resolved, remote, args.source_sha)
            execute('go_lifecycle_build', [args.go, 'build', '-o', go_consumer / 'lifecycle', '.'], go_consumer, go_env)
            execute('go_timeout_invalidation_cleanup', [go_consumer / 'lifecycle', native], go_consumer, go_env)
            execute('go_plugin_keys', [args.go, 'test', '-count=1', '-v', '.'], go_consumer, go_env)
            leftovers = list(Path(go_env['TMPDIR']).glob('mariamem-*'))
            if leftovers:
                raise ValueError('Go lifecycle left runtime/snapshot directories behind')
            report['go_lifecycle_cleanup'] = {'temporary_directories_removed': True}
            for mode, flag in (('valid', '--check-auth-keys'), ('missing', '--check-auth-keys-missing'),
                               ('corrupt', '--check-auth-keys-corrupt')):
                runtime_home = work / ('wasmer-' + mode)
                runtime_home.mkdir()
                result = execute('guest_keys_' + mode, [native / 'wasmer-headless', 'run',
                    native / 'mariamem.wasmu', '--no-tty', '--', flag], work,
                    {**env, 'WASMER_DIR': str(runtime_home)}, timeout=180, expected=None)
                step = report['steps']['guest_keys_' + mode]
                try:
                    step['checks'] = verify_guest_check(mode, result.returncode, result.stdout, result.stderr)
                except (ValueError, TypeError) as exc:
                    step.update(status='FAIL', error=str(exc))
                    raise
                save()
            execute('python_venv', [args.python, '-m', 'venv', work / 'venv'], work, env)
            python = work / 'venv/bin/python'
            execute('wheel_install', [python, '-m', 'pip', '--isolated', 'install', '--no-cache-dir',
                                     str(args.wheel) + '[test]'], work, env)
            tests = work / 'tests'
            (tests / 'consumer').mkdir(parents=True)
            (tests / 'evidence').mkdir()
            shutil.copy2(ROOT / 'tests/verify_alpha.py', tests / 'verify_alpha.py')
            shutil.copy2(ROOT / 'tests/consumer/test_database.py', tests / 'consumer/test_database.py')
            (tests / 'evidence/alpha-wheel.json').write_text(json.dumps({
                'wheel': str(args.wheel), 'sha256': args.wheel_sha256}))
            try:
                execute('installed_wheel_consumer', [python, tests / 'verify_alpha.py'], work, env, timeout=1500)
            finally:
                shutil.copytree(tests / 'evidence', evidence / 'wheel-consumer', dirs_exist_ok=True)
            alpha = json.loads((tests / 'evidence/alpha.json').read_text())
            if alpha.get('passed') is not True:
                raise ValueError('installed-wheel lifecycle acceptance lacks PASS')
            report['installed_wheel_acceptance'] = alpha
            shutil.copy2(ROOT / 'tests/consumer/test_ubuntu.py', work / 'test_platform.py')
            execute('python_platform_regressions', [python, '-m', 'pytest', '-q',
                    '--junitxml', evidence / 'python-platform.xml', work / 'test_platform.py'], work, env)
            (work / 'expected.json').write_text(json.dumps({
                'manifest': report['artifacts']['wheel_manifest'],
                'public_key': key_material()['public']}))
            (work / 'check_installed_keys.py').write_text(INSTALLED_CHECK)
            result = execute('installed_plugin_keys', [python, work / 'check_installed_keys.py'], work, env)
            report['installed_plugin_keys'] = json.loads(result.stdout)
        report['result'] = 'PASS'
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        save()
    print(json.dumps({'result': report['result'], 'evidence': str(report_path)}))
    return 0 if report['result'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-archive', type=Path, required=True)
    parser.add_argument('--native-sha256', required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--wheel-sha256', required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--target', choices=(DARWIN, UBUNTU), required=True)
    parser.add_argument('--evidence', type=Path, required=True, help='new directory for immutable evidence/logs')
    parser.add_argument('--go', default=shutil.which('go') or 'go')
    parser.add_argument('--python', default=sys.executable)
    args = parser.parse_args()
    for field, length in (('native_sha256', 64), ('wheel_sha256', 64), ('source_sha', 40)):
        value = getattr(args, field)
        if not re.fullmatch('[0-9a-f]{' + str(length) + '}', value):
            parser.error(field + ' must be a full lowercase hexadecimal hash')
    args.native_archive = args.native_archive.expanduser().resolve()
    args.wheel = args.wheel.expanduser().resolve()
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
