#!/usr/bin/env python3
"""Opt-in real source equality against frozen historical preparation producers.

No SDK/build/CI. Requires a clean candidate checkout, Git history, pinned archives
or network, and disposable scratch. Results describe source equality only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import fetch
from experiment_disk import DiskGuard, run_guarded
from guest_preparation_context import resolve
from git_identity import inspect_ref

PRODUCERS = [('12.3.3', 'legacy-full', '47121e1be0b399ba4e2270ce3e25c411ade0e2eb'),
             ('13.0.2', 'legacy-full', '32c799031f619164d3730b61a0bc9d7ae48dcd9b'),
             ('13.0.2', 'native-text', '4b3954a0faf42986459bc1ee68727be16d67bcbb')]


def inventory(root):
    rows = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if path.is_symlink():
            value = ['symlink', mode, os.readlink(path)]
        elif path.is_file():
            value = ['file', mode, hashlib.sha256(path.read_bytes()).hexdigest()]
        elif path.is_dir():
            value = ['directory', mode]
        else:
            raise ValueError('unexpected source member: ' + str(path))
        rows[path.relative_to(root).as_posix()] = value
    encoded = (json.dumps(rows, sort_keys=True, separators=(',', ':')) + '\n').encode()
    return rows, hashlib.sha256(encoded).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    scratch = args.scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)
    guard = DiskGuard(scratch, min_free_gib=12, budget_gib=6)
    candidate = inspect_ref(ROOT, 'HEAD').source_commit
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('comparison requires a clean frozen candidate')
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    records = []
    deadline = time.monotonic() + 3600
    def run(command, log):
        with log.open('w') as stream:
            code = run_guarded(command, guard, env=env, output=stream, timeout=max(1, deadline-time.monotonic()), interval=5)
        if code:
            raise ValueError('preparation failed; inspect ' + str(log))
    for engine, profile, origin in PRODUCERS:
        identity = inspect_ref(ROOT, origin)
        if identity.source_commit != origin or identity.object_type != 'commit':
            raise ValueError('historical producer is not an exact commit')
        label = engine + '-' + profile
        old = scratch / 'oracle'
        new = scratch / 'selected'
        result = resolve(ROOT, engine, profile)
        cache = scratch / 'downloads'
        for name in ('mariadb', 'lite4mariadb', 'libmariadb', 'wolfssl', 'pcre2', 'libfmt'):
            fetch(name, lock=result['effective_lock'], downloads=cache)
        subprocess.run(['git', 'worktree', 'add', '--detach', str(old), origin], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
        # Preserve the original experimental gate's exact-SHA detached CI path.
        env.update(GITHUB_SHA=origin, GITHUB_REF_NAME='experiment/issue134-oracle')
        (old / 'build').mkdir()
        (old / 'build/downloads').symlink_to(cache, target_is_directory=True)
        started = time.monotonic()
        run([sys.executable, str(old / 'scripts/prepare_guest.py')], args.evidence / (label + '-original.txt'))
        original_seconds = time.monotonic() - started
        before, before_hash = inventory(old / 'build/source')
        # Old output need not remain while new is prepared; compact identity is enough.
        shutil.rmtree(old / 'build')
        subprocess.run(['git', 'worktree', 'remove', str(old)], cwd=ROOT, check=True)
        started = time.monotonic()
        run([sys.executable, str(ROOT / 'scripts/prepare_guest.py'), '--engine', engine,
             '--profile', profile, '--work-dir', str(new), '--archive-cache', str(cache)],
            args.evidence / (label + '-selected.txt'))
        selected_seconds = time.monotonic() - started
        after, after_hash = inventory(new / 'source')
        different = [name for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)]
        records.append({'selection': result['selection'], 'original_source_commit': origin,
                        'engine_source_commit': result['guest_input']['source_commit'],
                        'tag_object_sha': result['guest_input']['tag_object_sha'],
                        'resolved_sha256': result['resolved_sha256'],
                        'members_original': len(before), 'members_selected': len(after),
                        'original_tree_sha256': before_hash, 'selected_tree_sha256': after_hash,
                        'different_paths': different, 'original_seconds': original_seconds,
                        'selected_seconds': selected_seconds,
                        'result': 'PASS' if not different else 'FAIL'})
        report = {'schema': 1, 'candidate_source_commit': candidate, 'scope': 'prepared source content/mode/link equality; no build/runtime acceptance',
                  'comparisons': records, 'disk': guard.check()}
        (args.evidence / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
        if different:
            raise ValueError('prepared source differs: ' + ', '.join(different[:10]))
        print(label, 'PASS', len(after), after_hash, flush=True)
        shutil.rmtree(new)
    print('All three prepared source trees match; archives remain for caller cleanup.', flush=True)


if __name__ == '__main__':
    main()
