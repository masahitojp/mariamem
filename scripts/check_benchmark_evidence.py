#!/usr/bin/env python3
"""Bound retained evidence, using an immutable migration baseline (Issue213)."""
import argparse
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'f6a4b6656f1a5a2cbc05e41e9ca697a8e8a42c93'
FILE_BYTES = 256 * 1024
CHANGE_BYTES = 1024 * 1024
CHANGE_FILES = 50
# C lowers the A1 migration cap by removing inspected redundant payloads.
CAPS = {'benchmarks/': (2025, 19384753),
        'docs/reviews/': (2697, 16658019),
        'docs/benchmarks/': (487, 2954424)}
CODE_SUFFIXES = {'.py', '.go', '.sh', '.c', '.h', '.cpp', '.js', '.mjs', '.ts', '.sql'}
CODE_NAMES = {'go.mod', 'go.sum', 'requirements.txt'}
PROTECTED = ('benchmarks/ucapreparedinput/', 'benchmarks/lexerpreparedinput/')
# Canonical generator input, copied by setup_candidate.py and installed by
# generate_runtime.py; not retained measurement evidence. Exact existing path only.
MAINTAINED_INPUTS = {'benchmarks/spikes/generated-go-integration/prepared-files.go.txt'}
PROVENANCE = 'benchmarks/forkcost/buffer-zero-candidate/build-evidence/previous-canonical-build.json'
# Only the A0 compact reports were reviewed for inert source-check selection.
# C must review other consumers before expanding this list.
INERT_PREFIXES = ('benchmarks/timer-product/', 'benchmarks/modelcase/results/',
                  'benchmarks/modelcase/shared-read-results/',
                  'benchmarks/prepared-output-20261114/', 'benchmarks/memoryea-product/')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


@lru_cache(maxsize=8)
def tree(root, ref):
    """Return path -> (bytes, Git blob identity), with exact commit validation."""
    actual = git(root, 'rev-parse', '--verify', ref + '^{commit}').decode().strip()
    if actual != ref:
        raise ValueError('evidence base must be an exact commit SHA')
    result = {}
    for row in git(root, 'ls-tree', '-rlz', ref, '--', *CAPS).split(b'\0'):
        if row:
            meta, path = row.split(b'\t')
            fields = meta.split()
            result[path.decode()] = (int(fields[3]), fields[2].decode())
    return result


def maintained(path):
    p = Path(path)
    return path in MAINTAINED_INPUTS or path.startswith(PROTECTED) or p.suffix in CODE_SUFFIXES or p.name in CODE_NAMES


def evidence(path, baseline):
    # Only reviewed existing code/input paths get exemptions. Unknown files,
    # including a new code suffix, count until deliberately reviewed here.
    for prefix in CAPS:
        if path.startswith(prefix):
            if prefix == 'benchmarks/' and path in baseline and maintained(path):
                return False
            return True
    return False


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def working_tree(root):
    paths = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *CAPS)
    result = {}
    for path in set(paths.decode().split('\0')) - {''}:
        p = Path(root) / path
        if p.is_symlink():
            raise ValueError('symlink in evidence set: ' + path)
        if p.is_file():
            data = p.read_bytes()
            result[path] = (len(data), blob(data))
    return result


def evaluate(current, baseline, base):
    errors, changed = [], []
    totals = {}
    for prefix, (count_cap, byte_cap) in CAPS.items():
        rows = {p: v for p, v in current.items() if p.startswith(prefix) and evidence(p, baseline)}
        count, size = len(rows), sum(v[0] for v in rows.values())
        totals[prefix] = {'files': count, 'bytes': size}
        if count > count_cap or size > byte_cap:
            errors.append(f'{prefix} cumulative evidence budget exceeded: {count} files / {size} bytes')
        for path, value in rows.items():
            if base.get(path) == value:
                continue
            changed.append(path)
            # Old oversized blobs are exempt only at their exact baseline path
            # and identity; relocation, growth and same-size edits are checked.
            if value[0] > FILE_BYTES and baseline.get(path) != value:
                errors.append(f'oversized evidence: {path} ({value[0]} bytes)')
    size = sum(current[p][0] for p in changed)
    if len(changed) > CHANGE_FILES or size > CHANGE_BYTES:
        errors.append(f'changed evidence budget exceeded: {len(changed)} files / {size} bytes')
    if errors:
        raise ValueError('\n'.join(errors))
    return {'passed': True, 'totals': totals, 'changed_files': len(changed), 'changed_bytes': size}


def check(root=ROOT, *, candidate=None, base=None):
    root = str(Path(root).resolve())
    baseline = tree(root, BASELINE)
    current = tree(root, candidate) if candidate else working_tree(root)
    # Local/archive-independent comparison is explicitly against migration
    # baseline when no event diff is supplied, never a guessed PR base.
    previous = tree(root, base) if base else baseline
    return evaluate(current, baseline, previous)


# C reviewed only these storage records; harness/recipe code remains conservative.
C_STORAGE_PATHS = {
    'benchmarks/forkcost/buffer-zero-candidate/README.md',
    'benchmarks/forkcost/buffer-zero-candidate/SHA256SUMS.json',
    'benchmarks/forkcost/buffer-zero-candidate/retention.json',
    'benchmarks/forkcost/buffer-zero-candidate/build-evidence/guest-build.txt',
    'benchmarks/forkcost/buffer-zero-candidate/build-evidence/guest-guest.json',
    'benchmarks/forkcost/buffer-zero-candidate/build-evidence/native-development.json',
    'benchmarks/forkcost/buffer-zero-candidate/validation/function-map.txt',
}


def known_inert(path, root=ROOT):
    if path in C_STORAGE_PATHS:
        return True
    baseline = tree(str(Path(root).resolve()), BASELINE)
    return (path.startswith(INERT_PREFIXES) and path in baseline
            and evidence(path, baseline) and path != PROVENANCE
            and not maintained(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-sha')
    parser.add_argument('--base-sha')
    args = parser.parse_args()
    base = args.base_sha
    if os.environ.get('GITHUB_EVENT_PATH') and base is None:
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        if os.environ.get('GITHUB_EVENT_NAME') == 'pull_request':
            base = event['pull_request']['base']['sha']
            if not base:
                raise ValueError('PR evidence base unavailable')
    result = check(candidate=args.candidate_sha, base=base)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
