#!/usr/bin/env python3
"""Private tagged-module/HTTP fixtures exercise real Start(Options{}); no publication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from package_native import payload, write_archive, verify_archive, encoded

MODULE = 'github.com/masahitojp/mariamem'
TAG = 'v0.3.0-alpha.999'  # Private fixture identity, never a requested/public release.


def prepare_fixture(root, native, work):
    source_manifest = json.loads((native / 'manifest.json').read_text())
    fixture_native = work / 'fixture-native'
    fixture_native.mkdir()
    for name in ('wasmer-headless', 'mariamem.wasmu', 'mariamem.wasmu.json'):
        shutil.copy2(native / name, fixture_native / name)
    source_manifest['package_version'] = '0.3.0a999'
    (fixture_native / 'manifest.json').write_bytes(encoded(source_manifest))
    files = payload(root, fixture_native, package_version='0.3.0a999')
    fixture = work / 'fixture'
    fixture.mkdir()
    target = source_manifest['platform']
    asset = f'mariamem-native-{target}.tar.gz'
    archive = fixture / asset
    write_archive(archive, files)
    verify_archive(archive, files)
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    sums = f'{archive_sha}  {asset}\n'.encode()
    (fixture / 'SHA256SUMS').write_bytes(sums)
    identity = {'tag': TAG, 'target': target, 'asset': asset,
                'archive_sha256': archive_sha, 'sums_sha256': hashlib.sha256(sums).hexdigest()}
    # Correct archive/checksum identity, but intentionally incompatible package
    # version: prove the full public startup rejects semantic mismatches too.
    wrong = dict(files)
    wrong_manifest = json.loads(wrong['manifest.json'])
    wrong_manifest['package_version'] = '0.2.0'
    wrong['manifest.json'] = encoded(wrong_manifest)
    incompatible = fixture / 'incompatible'
    incompatible.mkdir()
    write_archive(incompatible / asset, wrong)
    wrong_sha = hashlib.sha256((incompatible / asset).read_bytes()).hexdigest()
    wrong_sums = f'{wrong_sha}  {asset}\n'.encode()
    (incompatible / 'SHA256SUMS').write_bytes(wrong_sums)
    identity.update(wrong_archive_sha256=wrong_sha,
                    wrong_sums_sha256=hashlib.sha256(wrong_sums).hexdigest())
    (fixture / 'fixture.json').write_bytes(encoded(identity))
    return fixture, identity


def prepare_proxy(root, work):
    from consumer_module import prepare_proxy as tagged_proxy
    return tagged_proxy(root, work, TAG)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    native = args.native_dir.resolve()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('MARIAMEM_', 'MYSQLMEM_', 'GO', 'ZERO_', 'WASMER_', 'WASIX_'))}
    report = {'result': 'FAIL', 'source_sha': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'synthetic_release': True}
    try:
        with tempfile.TemporaryDirectory(prefix='mariamem-zero-setup-') as temporary:
            work = Path(temporary)
            fixture, identity = prepare_fixture(ROOT, native, work)
            report['fixture'] = identity
            report['native_manifest_sha256'] = hashlib.sha256((native / 'manifest.json').read_bytes()).hexdigest()
            proxy = prepare_proxy(ROOT, work)
            report["fixture_module_zip_sha256"] = hashlib.sha256((proxy / MODULE / "@v" / f"{TAG}.zip").read_bytes()).hexdigest()
            project = work / 'consumer'
            project.mkdir()
            source = (Path(__file__).with_name('zero_setup') / 'acceptance_test.go').read_text()
            # go test binaries omit module build identity; build an ordinary
            # consumer executable which runs the same bounded testing cases.
            source = source.replace('package acceptance', 'package main', 1)
            source += '\nfunc main() { testing.Main(func(string, string) (bool, error) { return true, nil }, []testing.InternalTest{{Name: "TestZeroSetup", F: TestZeroSetup}}, nil, nil) }\n'
            (project / 'main.go').write_text(source)
            (project / 'go.mod').write_text(f'module example.com/zero-setup-acceptance\n\ngo 1.26.0\n\nrequire {MODULE} {TAG}\n')
            tool_env = {**env, 'GOTOOLCHAIN': 'go1.26.8'}
            go_root = subprocess.check_output(['go', 'env', 'GOROOT'], env=tool_env, text=True).strip()
            go = str(Path(go_root) / 'bin/go')
            env.update(GOTOOLCHAIN='local', GOWORK='off' , GOPROXY=proxy.as_uri()+',https://proxy.golang.org',
                       GONOSUMDB=MODULE, GOMODCACHE=str(work / 'modules'),
                       ZERO_FIXTURE=str(fixture), ZERO_NATIVE=str(native), ZERO_EVIDENCE=str(output / 'cases.json'))
            subprocess.run([go, 'mod', 'tidy'], cwd=project, env=env, check=True)
            subprocess.run([go, 'build', '-race', '-mod=readonly', '-o', 'consumer', '.'], cwd=project, env=env, check=True)
            result = subprocess.run([str(project / 'consumer'), '-test.v'],
                                    cwd=project, env=env, text=True, capture_output=True, timeout=300)
            (output / 'consumer.log').write_text(result.stdout + result.stderr)
            print(result.stdout + result.stderr, flush=True)
            if result.returncode:
                raise RuntimeError(f'real zero-setup consumer failed: {output / "consumer.log"}')
            report['cases'] = json.loads((output / 'cases.json').read_text())
            report['result'] = 'PASS'
    finally:
        (output / 'summary.json').write_bytes(encoded(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
