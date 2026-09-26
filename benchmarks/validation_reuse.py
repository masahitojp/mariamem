#!/usr/bin/env python3
"""Disposable within-call AOT identity reuse experiment; never patches checkout."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def replace_once(root, path, old, new):
    target = root/path
    text = target.read_text()
    if text.count(old) != 1:
        raise ValueError(f'validation experiment anchor changed: {path}')
    target.write_text(text.replace(old, new))


def patch(root):
    # Public Resolve still digests every required artifact. ModuleBuild still
    # validates the sidecar and WASM build identity against that verified digest.
    replace_once(root, 'internal/snapshot/snapshot.go',
                 'func ModuleBuild(module string) (string, error) {',
                 'func ModuleBuild(module string, verified ...string) (string, error) {')
    replace_once(root, 'internal/snapshot/snapshot.go', '\thash, err := Digest(module)\n',
                 '\tvar hash string\n\tif len(verified) == 1 { hash = verified[0] } else { hash, err = Digest(module) }\n')
    replace_once(root, 'internal/artifacts/artifacts.go', 'snapshot.ModuleBuild(b.Module)',
                 'snapshot.ModuleBuild(b.Module, m.Hashes["mariamem.wasmu"])')
    replace_once(root, 'mariamem.go', '\ts, err := host.Start(startup,',
                 '\tstartup = context.WithValue(startup, "benchmark_verified_build", bundle.Build)\n\ts, err := host.Start(startup,')
    replace_once(root, 'internal/host/server.go', '\tbuild, metadataErr := snapshot.ModuleBuild(module)\n',
                 '\tbuild, _ := ctx.Value("benchmark_verified_build").(string)\n\tvar metadataErr error\n\tif build == "" { build, metadataErr = snapshot.ModuleBuild(module) }\n')
    files = ['internal/snapshot/snapshot.go', 'internal/artifacts/artifacts.go', 'mariamem.go', 'internal/host/server.go']
    return {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir', type=Path, required=True)
    parser.add_argument('--json', type=Path, required=True)
    args, extra = parser.parse_known_args()
    output = args.json.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT/'benchmarks/results'):
        parser.error('repository-local output must be under benchmarks/results/')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip():
        parser.error('experiment requires a committed source state')
    with tempfile.TemporaryDirectory(prefix='mariamem-validation-probe-') as temporary:
        root = Path(temporary)/'source'
        root.mkdir()
        archive = subprocess.check_output(['git', 'archive', source], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(root, filter='data')
        native = Path(temporary)/'native'
        original_native = args.native_dir.resolve()
        if any(p.is_symlink() for p in original_native.rglob('*')):
            raise ValueError('validation probe requires a regular-file native bundle')
        shutil.copytree(original_native, native, symlinks=False)
        before = hashes(native)
        for path in native.rglob('*'):
            if path.is_file():
                path.chmod(0o555 if path.stat().st_mode & 0o111 else 0o444)
        changed = patch(root)
        # Corruption/sidecar tests must still reject invalid input in the copy.
        subprocess.run(['go', 'test', './internal/artifacts', './internal/snapshot', './internal/host'], cwd=root, check=True)
        subprocess.run([sys.executable, 'benchmarks/go_isolation.py', '--native-dir', str(native),
                        '--json', str(output), *extra], cwd=root, check=True)
        if hashes(native) != before:
            raise RuntimeError('private native bundle changed during validation experiment')
        report = json.loads(output.read_text())
        report['environment']['commit'] = source
        report['experiment'] = {'name': 'within_call_aot_identity_reuse', 'source_commit': source,
                                'patched_source_sha256': changed, 'private_native_sha256': before,
                                'production_checkout_modified': False,
                                'scope': 'two redundant AOT digests only; manifest/artifact/sidecar and snapshot validation remain'}
        output.write_text(json.dumps(report, indent=2)+'\n')
    print(f'Experimental results: {output}')


if __name__ == '__main__':
    main()
