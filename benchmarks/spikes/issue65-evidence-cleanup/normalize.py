#!/usr/bin/env python3
"""Reproduce six path-only evidence normalizations from pinned Git raw bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = 'a5ee1ed9cc2c6932d317fba77c339b364acd48df'
RECEIPT = HERE / 'evidence/normalization.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def raw_bytes(path):
    return subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT)


def normalize(path, raw):
    """Replace exactly one machine directory; never parse/reserialize evidence."""
    if path.endswith('.json'):
        pattern = rb'("go_buildinfo": ")/[^"\n]+/(?=(?:wire|g2)\.test: )'
        replacement = rb'\1${HOST_BUILD}/'
    elif path.endswith('/initial-helper-read-failure.txt'):
        pattern = rb'(  File ")/[^"\n]+/(?=benchmarks/spikes/issue65-p1-timeout/build_checked_guest\.py")'
        replacement = rb'\1${CHECKED_WORKTREE}/'
    else:
        raise ValueError('unsupported evidence path')
    result, count = re.subn(pattern, replacement, raw)
    if count != 1:
        raise ValueError(f'expected one machine path in {path}, got {count}')
    return result


def verify():
    receipt = json.loads(RECEIPT.read_text())
    if receipt['raw_source_commit'] != BASE:
        raise ValueError('raw source identity changed')
    boundary = ROOT / 'benchmarks/spikes/issue65-p1-public/evidence/source-boundary.json'
    targets = json.loads(boundary.read_text())['unchanged_failure_files']
    if [r['path'] for r in receipt['files']] != targets:
        raise ValueError('six-file scope changed')
    for row in receipt['files']:
        raw = raw_bytes(row['path'])
        expected = normalize(row['path'], raw)
        actual = (ROOT / row['path']).read_bytes()
        if sha(raw) != row['raw_sha256']:
            raise ValueError('raw evidence hash changed: ' + row['path'])
        if sha(actual) != row['normalized_sha256'] or actual != expected:
            raise ValueError('path-only recipe mismatch: ' + row['path'])
    return len(targets)


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(f'Raw SHA256, exact path-only recipe and normalized SHA256 verified: {verify()} files')
