#!/usr/bin/env python3
"""Dry-run known disposable v0.4 outputs; --apply exports small evidence first."""
import argparse
import hashlib
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
# Explicit historical work outputs only. Never add source, caches or native inputs.
WORK_PATHS = ('build/generated-go-integration/final-stable-candidate',
 'build/generated-go-integration/llvm23-inspection',
 'build/generated-go-integration/llvm23-probe',
 'build/generated-go-integration/reproducible-audit',
 'build/generated-go-integration/llvm23-translation-1',
 'build/generated-go-integration/readiness-normal-check',
 'build/generated-go-integration/llvm23-madd-translation-2',
 'build/generated-go-integration/llvm23-bootstrap-replay',
 'build/generated-go-integration/io-audit',
 'build/generated-go-integration/repro-source-1',
 'build/generated-go-integration/readiness-ubuntu',
 'build/generated-go-integration/bound-candidate-allowed',
 'build/generated-go-integration/readiness-converter-replay',
 'build/generated-go-integration/llvm23-selected',
 'build/generated-go-integration/retranslated-import',
 'build/generated-go-integration/llvm23-six-clean',
 'build/generated-go-integration/bound-candidate',
 'build/generated-go-integration/readiness-converter-replay-2',
 'build/generated-go-integration/repro-normal-check',
 'build/generated-go-integration/llvm23-wasm-six-clean',
 'build/generated-go-integration/snapshot-audit',
 'build/generated-go-integration/final-fd-audit',
 'build/generated-go-integration/readiness-cleanroom',
 'build/generated-go-integration/preflight-native',
 'build/generated-go-integration/stable-fd',
 'build/generated-go-integration/llvm23-translation-2',
 'build/generated-go-integration/llvm23-madd-translation-1',
 'build/generated-go-integration/growth-fixed-candidate',
 'build/generated-go-integration/retranslated',
 'build/generated-go-integration/stable-fd-v2',
 'build/generated-go-integration/growth-check-source',
 'build/generated-go-integration/repro-source-2',
 'build/generated-go-integration/stable-fd-native',
 'build/generated-go-integration/bound-candidate-v2',
 'tests/runs',
 'benchmarks/results',
 'build/wasm2go-legacy-eh/source',
 'build/wasm2go-legacy-eh/artifact',
 'build/wasm2go-legacy-eh/product',
 'build/wasm2go-legacy-eh/probe')
EVIDENCE_SUFFIXES = {'.json', '.log', '.csv', '.xml'}
SKIP_DIRS = {'source', 'module', 'converter', '.git', '.venv', 'venv', '__pycache__', 'node_modules'}
MAX_EVIDENCE_BYTES = 10 * 1024 * 1024


def targets(root):
    root = Path(root).resolve()
    result = []
    for name in WORK_PATHS:
        path = root / name
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or path.resolve() != path.absolute():
            raise ValueError('refusing symlink target or ancestor: ' + name)
        if not path.is_dir():
            raise ValueError('expected disposable directory: ' + name)
        result.append(path)
    return result


def size(path):
    return int(subprocess.check_output(['du', '-sk', str(path)], text=True).split()[0]) * 1024


def export_evidence(root, paths, destination):
    root = Path(root).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('evidence destination must be fresh')
    if any(destination == p or p in destination.parents for p in paths):
        raise ValueError('evidence destination is inside a cleanup target')
    records = []
    destination.mkdir(parents=True)
    for target in paths:
        for directory, dirs, files in os.walk(target, followlinks=False):
            base = Path(directory)
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (base/d).is_symlink()]
            for name in files:
                path = base/name
                if path.is_symlink() or path.suffix not in EVIDENCE_SUFFIXES:
                    continue
                rel = path.relative_to(root)
                count = path.stat().st_size
                record = {'path':str(rel), 'bytes':count, 'copied':count <= MAX_EVIDENCE_BYTES}
                if record['copied']:
                    out = destination/rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    data = path.read_bytes()
                    record['sha256'] = hashlib.sha256(data).hexdigest()
                    if count > 64 * 1024:
                        out = out.with_name(out.name+'.gz')
                        with out.open('wb') as raw:
                            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
                                compressed.write(data)
                        if gzip.decompress(out.read_bytes()) != data:
                            raise ValueError('evidence compression verification failed')
                    else:
                        shutil.copy2(path, out)
                    record['stored_path'] = str(out.relative_to(destination))
                    record['stored_bytes'] = out.stat().st_size
                records.append(record)
    (destination/'export.json').write_text(json.dumps(records, indent=2)+'\n')
    return records


def validate_ignored(root, paths):
    # Do not depend solely on the allowlist: reject any tracked file and any
    # path that ceased to be ignored. Never offer an override for these gates.
    tracked = subprocess.check_output(['git','ls-files','-z'], cwd=root).decode().split('\0')
    for p in paths:
        rel = str(p.relative_to(root))
        if any(name == rel or name.startswith(rel+'/') for name in tracked if name):
            raise ValueError('tracked source under cleanup target: '+rel)
        if subprocess.run(['git','check-ignore','--quiet',rel], cwd=root).returncode:
            raise ValueError('cleanup target is not ignored: '+rel)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='delete only the fixed allowlist after exporting small evidence')
    parser.add_argument('--dry-run', action='store_true', help='explicit default; cannot be combined with --apply')
    parser.add_argument('--evidence-dir', type=Path, help='required fresh destination for --apply')
    args = parser.parse_args()
    if args.apply and (args.dry_run or not args.evidence_dir):
        parser.error('--apply requires --evidence-dir and excludes --dry-run')
    paths = targets(ROOT)
    validate_ignored(ROOT, paths)
    total = 0
    for path in paths:
        count = size(path); total += count
        print(f'{count/1024**3:7.2f} GiB {path.relative_to(ROOT)}', flush=True)
    print(f'Estimated removable: {total/1024**3:.2f} GiB (du allocation; APFS sharing may differ)', flush=True)
    if not args.apply:
        print('DRY RUN: no files removed')
        return
    export_evidence(ROOT, paths, args.evidence_dir)
    for path in paths:
        # Recheck boundary just before mutation.
        if path.is_symlink() or path.resolve() != path.absolute():
            raise ValueError('cleanup target changed: '+str(path))
        shutil.rmtree(path)
        print('REMOVED '+str(path.relative_to(ROOT)), flush=True)


if __name__ == '__main__':
    main()
