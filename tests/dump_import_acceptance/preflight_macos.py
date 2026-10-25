"""Test-only acquisition preflight; never produces/imports a dump."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import tarfile
import time


def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--bottle-key', default='arm64_golden_gate')
    parser.add_argument('--formula-json', type=Path)
    parser.add_argument('--formula-source', type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    temp, evidence = workspace / 'temp', workspace / 'evidence'
    report = {'result': 'FAIL', 'stage': 'acquisition',
              'platform': platform.platform(), 'architecture': platform.machine(),
              'source_commit': json.loads(subprocess.check_output(
                  ['python3', 'scripts/git_identity.py', 'inspect', 'HEAD'], text=True))['source_commit'],
              'formula_commit': '1db0348859ae3b2e0de9babe91dfb3673bdfb729',
              'dump_generated': False, 'reader_executed': False}
    process = None
    try:
        assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
        formula = json.loads((args.formula_json or evidence / 'homebrew-formula.json').read_text())
        assert formula['versions']['stable'] == '12.3.3'
        if args.formula_source:
            formula_bytes = args.formula_source.read_bytes()
        else:
            content = json.loads(subprocess.check_output(['gh', 'api',
                'repos/Homebrew/homebrew-core/contents/Formula/m/mariadb@12.3.rb?ref='
                + report['formula_commit']], text=True))
            formula_bytes = base64.b64decode(content['content'])
        assert hashlib.sha256(formula_bytes).hexdigest() == formula['ruby_source_checksum']['sha256']
        (evidence / 'mariadb@12.3.rb').write_bytes(formula_bytes)
        bottle = temp / ('mariadb-12.3.3.'+args.bottle_key+'.bottle.tar.gz')
        pin = formula['bottle']['stable']['files'][args.bottle_key]
        assert sha(bottle) == pin['sha256']
        report['bottle'] = pin
        excluded = []
        def safe_filter(member, destination):
            try:
                return tarfile.data_filter(member, destination)
            except tarfile.LinkOutsideDestinationError:
                # An unused service symlink is not installed outside scratch.
                excluded.append({'path': member.name, 'target': member.linkname})
                return None
        extraction = temp / 'macos-native'
        with tarfile.open(bottle) as archive:
            archive.extractall(extraction, filter=safe_filter)
        report['excluded_external_symlinks'] = excluded
        native = extraction / 'mariadb@12.3/12.3.3_1'
        # Relocate the bottle's install-name placeholders inside owned scratch.
        # Shell-launched bootstrap strips DYLD_* on macOS, so environment-only
        # relocation is insufficient. No native source/runtime patch is applied.
        libraries = [Path('/opt/homebrew/opt') / name / 'lib'
                     for name in ['openssl@4', 'pcre2', 'lz4', 'xz', 'zstd']]
        env = dict(os.environ, DYLD_LIBRARY_PATH=':'.join(map(str, libraries)))
        report['environment'] = {'DYLD_LIBRARY_PATH': env['DYLD_LIBRARY_PATH']}
        report['dependencies'] = {}
        for library in libraries:
            receipt = library.parent / 'INSTALL_RECEIPT.json'
            report['dependencies'][str(library)] = {
                'realpath': str(library.resolve()),
                'receipt': json.loads(receipt.read_text()),
                'dylibs': {p.name: sha(p) for p in library.glob('*.dylib') if p.is_file()}}
        def run(name, command, timeout=60):
            result = subprocess.run(list(map(str, command)), env=env,
                                    capture_output=True, timeout=timeout)
            (evidence / (name + '.stdout.txt')).write_bytes(result.stdout)
            (evidence / (name + '.stderr.txt')).write_bytes(result.stderr)
            report.setdefault('commands', []).append({
                'argv': list(map(str, command)), 'exit_code': result.returncode,
                'stdout': name + '.stdout.txt', 'stderr': name + '.stderr.txt'})
            if result.returncode:
                raise RuntimeError(f'{name}: exit {result.returncode}')
            return result.stdout.decode()
        report['relocations'] = []
        for name in ['mariadbd', 'mariadb', 'mariadb-dump', 'my_print_defaults',
                     'resolveip', 'mariadb-admin']:
            binary = native / 'bin' / name
            before = sha(binary)
            loader = subprocess.check_output(['otool', '-L', str(binary)], text=True)
            changes = []
            for line in loader.splitlines()[1:]:
                original = line.strip().split(' (', 1)[0]
                if original.startswith('@@HOMEBREW_PREFIX@@/'):
                    replacement = original.replace('@@HOMEBREW_PREFIX@@', '/opt/homebrew')
                    assert Path(replacement).exists(), replacement
                    subprocess.run(['install_name_tool', '-change', original, replacement,
                                    str(binary)], check=True, capture_output=True)
                    changes.append([original, replacement])
            if changes:
                subprocess.run(['codesign', '--force', '--sign', '-', str(binary)],
                               check=True, capture_output=True)
            report['relocations'].append({'binary': name, 'before_sha256': before,
                                           'after_sha256': sha(binary), 'changes': changes})
        report['stage'] = 'binary_identity'
        report['executables'] = {}
        for name in ['mariadbd', 'mariadb', 'mariadb-dump']:
            binary = native / 'bin' / name
            report['executables'][name] = {
                'sha256': sha(binary), 'file': run(name + '-file', ['file', binary]).strip(),
                'loader': run(name + '-loader', ['otool', '-L', binary]),
                'version': run(name + '-version', [binary, '--no-defaults', '--version']).strip()}
            assert '12.3.3' in report['executables'][name]['version']
            assert 'arm64' in report['executables'][name]['file']
        help_text = run('mariadb-dump-help', [native/'bin/mariadb-dump', '--no-defaults', '--help'])
        for option in ['routines', 'triggers', 'events', 'hex-blob', 'default-character-set',
                       'single-transaction', 'tz-utc', 'order-by-primary', 'dump-date',
                       'lock-tables', 'add-locks']:
            assert option in help_text, option
        report['skip_definer_help_present'] = 'skip-definer' in help_text
        report['stage'] = 'initialize'
        data = temp / 'macos-relocated-data'
        socket_path = temp / 'm.sock'
        assert not data.exists(), 'preflight requires a fresh datadir'
        run('macos-install-db', [native/'bin/mariadb-install-db', '--no-defaults',
            '--basedir='+str(native), '--datadir='+str(data),
            '--auth-root-authentication-method=normal', '--skip-test-db'], timeout=120)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        report['stage'] = 'startup_query'
        command = [str(native/'bin/mariadbd'), '--no-defaults', '--basedir='+str(native),
                   '--datadir='+str(data), '--socket='+str(socket_path),
                   '--pid-file='+str(temp/'macos-native.pid'), '--port='+str(port),
                   '--bind-address=127.0.0.1', '--character-set-server=utf8mb4',
                   '--collation-server=utf8mb4_unicode_ci']
        report['server_command'] = command
        with (evidence/'macos-server.log').open('wb') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            deadline = time.monotonic() + 40
            while not socket_path.exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('native server startup failed/timed out')
                time.sleep(.2)
            output = run('macos-native-query', [native/'bin/mariadb', '--no-defaults',
                '--protocol=tcp', '--host=127.0.0.1', '--port='+str(port), '--user=root',
                '--batch', '--skip-column-names', '--execute=SELECT VERSION(), @@version_compile_machine; '
                "SELECT user,host FROM mysql.user WHERE user='root' AND host='localhost'; SELECT 1;"])
            assert '12.3.3' in output and 'root\tlocalhost' in output
        report['result'] = 'PASS'
        report['stage'] = 'complete'
    except Exception as error:
        report['error'] = str(error)
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            report['server_reaped'] = process.poll() is not None
        (evidence/'macos-preflight.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: report.get(k) for k in ['result', 'stage', 'error', 'server_reaped']}))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
