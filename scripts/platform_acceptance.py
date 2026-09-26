#!/usr/bin/env python3
"""Run archive-only acceptance from a temporary external Go module; never edit reviews."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import shlex
import signal
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from native_target import DARWIN, UBUNTU, target_metadata, manifest_target

MODULE = 'github.com/masahitojp/mariamem'
BUNDLE = 'mariamem-native-darwin-arm64'
ARTIFACTS = ('wasmer-headless', 'mariamem.wasmu', 'mariamem.wasmu.json')
STEPS = ('environment', 'archive_sha256', 'extract', 'executable_permission', 'artifact_hashes',
         'external_module', 'module_fetch', 'consumer_build', 'NativeDir', 'Start',
         'database_sql_connection', 'SELECT_1', 'MariaDB_version', 'multi_client', 'InnoDB_transaction',
         'WaitDisconnected', 'Snapshot', 'source_closed', 'Fork_A', 'Fork_B',
         'fork_isolation', 'close_cleanup', 'consumer', 'harness_cleanup')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def eligible(version, arch):
    return version.split('.')[0] == '15' and arch == 'arm64'


def verify_resolved_commit(resolved, expected, requested_tag=None):
    """Bind a CI candidate's public Go module to the exact build commit."""
    if resolved.get('Path') != MODULE or not resolved.get('Version') or not resolved.get('Sum'):
        raise ValueError('public module identity/version/checksum is incomplete')
    if requested_tag and resolved.get('Version') != requested_tag:
        raise ValueError('public module version differs from requested release tag')
    origin = resolved.get('Origin') or {}
    actual = origin.get('Hash')
    if actual != expected:
        raise ValueError(f'public module commit mismatch: expected {expected}, resolved {actual or "unknown"}')


def bind_remote_origin(resolved, remote, expected, requested_tag=None):
    """Match proxy-fetched module identity to a direct immutable remote query."""
    if any(remote.get(key) != resolved.get(key) for key in ('Path', 'Version')):
        raise ValueError('direct remote module identity/version differs from fetched module')
    bound = {**resolved, 'Origin': remote.get('Origin') or {}}
    verify_resolved_commit(bound, expected, requested_tag)
    return bound


def extract(archive, destination, target=DARWIN):
    bundle = target_metadata(target)["bundle_name"]
    seen = set()
    with tarfile.open(archive, 'r:gz') as tar:
        for m in tar:
            p = PurePosixPath(m.name)
            if (p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != bundle
                    or p.as_posix() in seen or not (m.isfile() or m.isdir())):
                raise ValueError('unsafe/duplicate archive member: ' + m.name)
            seen.add(p.as_posix())
            target = destination.joinpath(*p.parts)
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(m) as src, target.open('xb') as out:
                    shutil.copyfileobj(src, out)
                target.chmod(m.mode & 0o777)
    return destination / bundle


def check_artifacts(native, target=DARWIN):
    manifest = json.loads((native / 'manifest.json').read_text())
    hashes = {name: digest(native / name) for name in ARTIFACTS}
    if manifest.get("platform") != target or manifest.get("version") != 1:
        raise ValueError("unexpected native manifest")
    manifest_target(manifest)
    if target == DARWIN and manifest.get("minimum_macos") != 15:
        raise ValueError("unexpected native manifest")
    if any(manifest['sha256'].get(name) != value for name, value in hashes.items()):
        raise ValueError('native artifact hash mismatch')
    sidecar = json.loads((native / 'mariamem.wasmu.json').read_text())
    if sidecar['module_sha256'] != hashes['mariamem.wasmu']:
        raise ValueError('guest sidecar mismatch')
    return {'files': hashes, 'guest_wasm_sha256': sidecar['wasm_sha256']}


def isolated_env(work):
    env = {k: v for k, v in os.environ.items() if k not in ('GH_TOKEN', 'GITHUB_TOKEN') and not k.startswith(('GO', 'MARIAMEM_', 'WASMER_', 'WASIX_', 'DYLD_', 'LD_'))}
    env.update(GOWORK='off', GOENV='off', GOFLAGS='-modcacherw', GOTOOLCHAIN='local', CGO_ENABLED='0',
               GO111MODULE='on', GOPROXY='https://proxy.golang.org,direct', GOSUMDB='sum.golang.org',
               GOPATH=str(work / 'gopath'), GOMODCACHE=str(work / 'modcache'),
               GOCACHE=str(work / 'gocache'), TMPDIR=str(work / 'runtime-tmp'))
    (work / 'runtime-tmp').mkdir()
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=(DARWIN, UBUNTU), default=DARWIN)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--module', required=True, help='public commit, tag or pseudo-version (no local replace)')
    parser.add_argument('--expected-commit', help='exact public build commit (40 hexadecimal characters)')
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--go', default='go', help='Go executable; requires a toolchain supporting the module')
    parser.add_argument('--dry-run', action='store_true', help='archive/environment checks only; never acceptance PASS')
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-fA-F]{64}', args.sha256):
        parser.error('--sha256 must be 64 hexadecimal characters')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.\-]*', args.module):
        parser.error('--module must be a commit/tag/pseudo-version')
    if args.expected_commit and not re.fullmatch('[0-9a-fA-F]{40}', args.expected_commit):
        parser.error('--expected-commit must be a full 40-character Git commit')
    release_tag = bool(re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-(?:alpha|beta|rc)\.[0-9]+)?', args.module))
    if args.expected_commit and args.module.lower() != args.expected_commit.lower() and not release_tag:
        parser.error('--module must be the exact commit or an immutable SemVer release tag')
    output = args.evidence.expanduser().resolve()
    if output.exists() or output.with_suffix('.log').exists():
        parser.error('evidence/log already exists; choose a new output path')
    output.parent.mkdir(parents=True, exist_ok=True)
    archive = args.archive.expanduser().resolve()
    evidence = {'schema_version': 1, 'target': args.target, 'started_at': datetime.now(timezone.utc).isoformat(),
                'mode': 'dry-run' if args.dry_run else 'acceptance', 'result': 'FAIL',
                'platform_acceptance_passed': False, 'module_requested': MODULE + '@' + args.module,
                'expected_source_commit': args.expected_commit.lower() if args.expected_commit else None,
                'archive': {'filename': archive.name, 'expected_sha256': args.sha256.lower()},
                'steps': {s: {'status': 'NOT_RUN'} for s in STEPS}, 'consumer_events': []}
    work = None
    current = 'environment'
    log = output.with_suffix('.log')

    def save():
        output.write_text(json.dumps(evidence, indent=2) + '\n')

    def execute(argv, cwd=None, env=None, timeout=900):
        result = subprocess.run(argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout)
        with log.open('a') as stream:
            stream.write(json.dumps(argv) + '\n' + result.stdout + result.stderr + '\n')
        if result.returncode:
            raise RuntimeError('command failed (exit %d); see %s: %s' % (result.returncode, log.name, result.stderr[-2000:]))
        return result.stdout.strip()

    def begin(name):
        nonlocal current
        current = name
        evidence['steps'][name] = {'status': 'RUNNING'}
        save()

    def passed(details=None):
        evidence['steps'][current] = {'status': 'PASS'}
        if details is not None:
            evidence['steps'][current]['details'] = details
        save()

    try:
        begin('environment')
        evidence['environment'] = {}
        commands = ([('sw_vers', ['/usr/bin/sw_vers']),
                     ('product_version', ['/usr/bin/sw_vers', '-productVersion'])]
                    if args.target == DARWIN else [('os_release', ['cat', '/etc/os-release']),
                                                  ('system', ['/usr/bin/uname', '-s'])])
        commands += [('architecture', ['/usr/bin/uname', '-m']),
                     ('go_version', [args.go, 'version'])]
        for key, command in commands:
            evidence['environment'][key] = execute(command)
            save()
        e = evidence['environment']
        if args.target == DARWIN:
            evidence['target_matches'] = eligible(e['product_version'], e['architecture'])
        else:
            release = dict(line.split('=', 1) for line in shlex.split(e['os_release'], comments=True)
                           if '=' in line)
            e['distribution'], e['version_id'] = release.get('ID'), release.get('VERSION_ID')
            evidence['target_matches'] = (e['system'] == 'Linux' and e['architecture'] == 'x86_64'
                                          and e['distribution'] == 'ubuntu' and e['version_id'] == '24.04')
        if not args.dry_run and not evidence['target_matches']:
            raise RuntimeError('acceptance requires ' + args.target + '; use --dry-run for preparation elsewhere')
        passed()
        begin('archive_sha256')
        evidence['archive']['sha256'] = digest(archive)
        if evidence['archive']['sha256'] != args.sha256.lower():
            raise ValueError('archive SHA256 mismatch')
        passed()
        work = Path(tempfile.mkdtemp(prefix='mariamem-acceptance-')).resolve()
        begin('extract')
        native = extract(archive, work / 'unpacked', args.target)
        passed()
        begin('executable_permission')
        runtime = native / 'wasmer-headless'
        if not runtime.is_file() or not runtime.stat().st_mode & 0o111 or not os.access(runtime, os.X_OK):
            raise ValueError('extracted runtime lacks executable permission')
        passed()
        begin('artifact_hashes')
        evidence['artifacts'] = check_artifacts(native, args.target)
        passed()
        if args.dry_run:
            evidence['result'] = 'DRY_RUN'
        else:
            env = isolated_env(work)
            consumer = work / 'consumer'
            consumer.mkdir()
            begin('external_module')
            execute([args.go, 'mod', 'init', 'example.com/mariamem-platform-acceptance'], consumer, env)
            shutil.copyfile(Path(__file__).with_suffix('') / 'consumer.go', consumer / 'main.go')
            passed()
            begin('module_fetch')
            execute([args.go, 'get', MODULE + '@' + args.module, 'github.com/go-sql-driver/mysql@v1.9.3'], consumer, env)
            resolved = json.loads(execute([args.go, 'list', '-m', '-json', MODULE], consumer, env))
            if resolved.get('Replace'):
                raise ValueError('local module replacement is forbidden')
            if args.expected_commit:
                # Proxy responses need not contain Origin. Query the exact SHA
                # or release tag directly, then bind its commit and version.
                remote = json.loads(execute(
                    [args.go, 'list', '-m', '-json', MODULE + '@' + (args.module if release_tag else args.expected_commit.lower())],
                    consumer, {**env, 'GOPROXY': 'direct'}))
                resolved = bind_remote_origin(resolved, remote, args.expected_commit.lower(),
                                              args.module if release_tag else None)
            evidence['module_resolved'] = {k: resolved[k] for k in ('Path', 'Version', 'Sum', 'Origin') if k in resolved}
            passed()
            begin('consumer_build')
            executable = consumer / 'acceptance'
            execute([args.go, 'build', '-o', str(executable), '.'], consumer, env)
            passed()
            begin('consumer')
            # Stream step events, so a runtime failure leaves the last started step on disk.
            with log.open('a') as stderr:
                proc = subprocess.Popen([str(executable), str(native)], cwd=consumer, env=env,
                                        text=True, stdout=subprocess.PIPE, stderr=stderr)
                try:
                    for line in proc.stdout:
                        item = json.loads(line)
                        evidence['consumer_events'].append(item)
                        if item['step'] in evidence['steps'] and item['status'] != 'INFO':
                            evidence['steps'][item['step']] = item
                        save()
                    code = proc.wait()
                finally:
                    if proc.poll() is None:
                        proc.send_signal(signal.SIGINT)
                        # Let consumer defers close the guest before removing its files.
                        proc.wait()
            if code or any(evidence['steps'][s]['status'] != 'PASS' for s in STEPS if s != 'harness_cleanup'):
                raise RuntimeError('consumer acceptance failed; see step results and log')
            evidence['result'] = 'PASS'
    except (Exception, KeyboardInterrupt) as exc:
        evidence['result'] = 'FAIL'
        failed_step = current
        if current == 'consumer':
            failed = [e['step'] for e in evidence['consumer_events'] if e['status'] == 'FAIL']
            running = [e['step'] for e in evidence['consumer_events'] if e['status'] == 'RUNNING']
            failed_step = (failed or running[-1:] or [current])[0]
        evidence['failure'] = {'step': failed_step, 'error': str(exc)}
        evidence['steps'][current] = {'status': 'FAIL', 'error': str(exc)}
    finally:
        try:
            if work is not None:
                shutil.rmtree(work)
            evidence['steps']['harness_cleanup'] = {'status': 'PASS'}
        except OSError as exc:
            evidence['steps']['harness_cleanup'] = {'status': 'FAIL', 'error': str(exc)}
            evidence['result'] = 'FAIL'
        evidence['platform_acceptance_passed'] = evidence['result'] == 'PASS' and evidence.get('target_matches', False)
        evidence['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps({'result': evidence['result'], 'platform_acceptance_passed': evidence['platform_acceptance_passed'],
                      'evidence': str(output)}))
    return 1 if evidence['result'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
