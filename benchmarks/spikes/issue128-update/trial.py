#!/usr/bin/env python3
"""Finite source-only diagnostic; never produces a qualified preparation/build."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = ROOT / 'build/issue128-temp'
EVIDENCE = Path(__file__).resolve().parent / 'evidence'
sys.path.insert(0, str(ROOT / 'scripts'))
from common import digest, extract  # noqa: E402
from git_identity import inspect_ref, require_commit  # noqa: E402
from experiment_disk import DiskGuard  # noqa: E402

TARGET = '620a4b5624222048fece7fe1789978ae0675cae2'
BASE = '83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e'
CANDIDATES = {
    'legacy': '47121e1be0b399ba4e2270ce3e25c411ade0e2eb',
    'old-native': 'be244a0bdb510a22417241c2aa2f76a9093aac1b',
    'native': '8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3',
}


def save(name, value):
    (EVIDENCE / name).write_text(json.dumps(value, indent=2) + '\n')


def command(args, cwd=None):
    start = time.monotonic()
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    return {'argv': args, 'returncode': result.returncode,
            'wall_seconds': time.monotonic() - start, 'output': result.stdout}


def fetch():
    repo = SCRATCH / 'identity.git'
    subprocess.run(['git', 'init', '--bare', str(repo)], check=True)
    records = []
    for tag in ('mariadb-12.3.3', 'mariadb-13.0.2'):
        result = command(['git', '-C', str(repo), 'fetch', '--depth=1',
                          '--filter=blob:none', 'https://github.com/MariaDB/server.git',
                          f'refs/tags/{tag}:refs/tags/{tag}'])
        records.append(result)
        save('fetch-commands.json', records)
        if result['returncode']:
            raise RuntimeError('official identity fetch failed')
    identities = {}
    for tag, expected in [('mariadb-12.3.3', BASE), ('mariadb-13.0.2', TARGET)]:
        identity = inspect_ref(repo, tag)
        require_commit(repo, expected)
        assert identity.object_type == 'tag' and identity.source_commit == expected
        identities[tag] = {'tag_object_sha': identity.object_sha,
                           'source_commit': identity.source_commit,
                           'object_type': identity.object_type}
    identities['candidates'] = {}
    for name, sha in CANDIDATES.items():
        require_commit(ROOT, sha)
        identities['candidates'][name] = {'source_commit': sha}
    save('source-identities.json', identities)
    inputs = json.loads((ROOT / 'release/inputs.lock.json').read_text())['inputs']
    downloads = [('target', f'https://codeload.github.com/MariaDB/server/tar.gz/{TARGET}', None)]
    for name in ('mariadb', 'lite4mariadb'):
        entry = next(e for e in inputs if e['name'] == name)
        downloads.append((name, entry['url'], entry['sha256']))
    records = []
    for name, url, expected in downloads:
        path = SCRATCH / f'{name}.tar.gz'
        result = command(['curl', '--fail', '--location', '--retry', '2',
                          '--max-time', '300', '--output', str(path), url])
        result.update(name=name, url=url)
        records.append(result)
        save('download-commands.json', records)
        if result['returncode']:
            raise RuntimeError('source archive download failed')
        actual = digest(path)
        if expected and actual != expected:
            raise ValueError('locked archive hash mismatch')
        result.update(sha256=actual, bytes=path.stat().st_size)
        save('download-commands.json', records)


def load_module(name, root):
    # Candidate modules share common.ROOT by import; bind it before loading.
    for key in list(sys.modules):
        if key in ('common', 'guest_input', 'uca_prepared', 'prepared_source_patch',
                   'guest_init_hooks', 'guest_auth_hooks', 'routine_schema'):
            del sys.modules[key]
    sys.path.insert(0, str(root / 'scripts'))
    return importlib.import_module(name)


def attempt(label, function, records):
    start = time.monotonic()
    try:
        result = function()
        records.append({'stage': label, 'status': 'PASS', 'result': result,
                        'wall_seconds': time.monotonic() - start})
    except Exception as error:
        records.append({'stage': label, 'status': 'FAIL',
                        'exception': type(error).__name__, 'error': str(error),
                        'wall_seconds': time.monotonic() - start})


def trial(adapted=False):
    guard = DiskGuard(SCRATCH, 12, 2)
    storage = [guard.check()]
    recipe = SCRATCH / 'recipe'
    if not recipe.exists():
        extract(SCRATCH / 'lite4mariadb.tar.gz', recipe)
    recipe = next(recipe.iterdir())
    results = {}
    for name, sha in CANDIDATES.items():
        started = time.monotonic()
        root = SCRATCH / ('candidate-' + name)
        root.mkdir()
        paths = ['scripts', 'guest', 'release/inputs.lock.json', 'tests/fixtures']
        if subprocess.run(['git', 'cat-file', '-e', sha + ':benchmarks/ucapreparedinput'],
                          capture_output=True).returncode == 0:
            paths.append('benchmarks/ucapreparedinput')
        archive = subprocess.check_output(['git', 'archive', sha, *paths])
        candidate_tar = SCRATCH / 'candidate.tar'
        candidate_tar.write_bytes(archive)
        with tarfile.open(candidate_tar) as source_archive:
            source_archive.extractall(root, filter='data')
        candidate_tar.unlink()
        source_parent = SCRATCH / 'source'
        extract(SCRATCH / 'target.tar.gz', source_parent)
        source = next(source_parent.iterdir())
        pin = json.loads((root / 'guest/input.json').read_text())
        for relative, expected in pin['recipe_files_sha256'].items():
            assert digest(recipe / relative) == expected
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(recipe / relative, target)
        storage.append(guard.check())
        records = []
        source_input = next(e for e in json.loads((root / 'release/inputs.lock.json').read_text())['inputs']
                            if e['name'] == 'mariadb')
        records.append({'stage': 'locked-source-archive', 'status': 'FAIL',
                        'expected_sha256': source_input['sha256'],
                        'actual_sha256': digest(SCRATCH / 'target.tar.gz'),
                        'note': 'Original fetch would reject the target before extraction; diagnostic tree only.'})
        if (root / 'scripts/uca_prepared.py').exists():
            uca = load_module('uca_prepared', root)
            attempt('unchanged-UCA-pristine-guard', lambda: uca.prepare(root, source), records)
        guest_input = load_module('guest_input', root)
        attempt('unchanged-series-preimage-guard',
                lambda: guest_input.apply_series(root, source, pin), records)
        # Independent diagnostic after strict guard failure: no validator is changed.
        # Record every drifted preimage and run original patches with fuzz=0.
        for patch in pin['patches']:
            drift = {relative: {'expected': expected,
                               'actual': digest(source / relative) if (source / relative).exists() else None}
                     for relative, expected in patch['before_sha256'].items()
                     if (digest(source / relative) if (source / relative).exists() else None) != expected}
            patch_path = root / patch['file']
            if adapted and patch_path.name in ('12.3.3-redo.patch', '12.3.3-prepared.patch'):
                replacement = 'redo.patch' if 'redo' in patch_path.name else 'prepared.patch'
                patch_path = EVIDENCE.parent / 'adaptations' / replacement
                inventory = json.loads((EVIDENCE / 'surface-inventory.json').read_text())
                relative = ('storage/innobase/log/log0log.cc' if replacement == 'redo.patch'
                            else 'sql/sql_prepare.cc')
                assert digest(source / relative) == inventory[relative]['target_sha256']
            result = command(['patch', '--batch', '--forward', '--fuzz=0', '-p1',
                              '-i', str(patch_path)], source)
            result.update(stage=patch['file'], preimage_drift=drift,
                          status='DIAGNOSTIC_ONLY', patch_sha256=digest(patch_path))
            records.append(result)
        for relative in ('guest/source.patch', 'guest/experimental.patch'):
            if (root / relative).exists():
                patch_path = root / relative
                if adapted and relative == 'guest/source.patch':
                    patch_path = EVIDENCE.parent / 'adaptations' / (name + '-source.patch')
                    review = json.loads((EVIDENCE.parent / 'adaptations/review.json').read_text())
                    assert digest(source / 'storage/innobase/buf/buf0flu.cc') == review[
                        'storage/innobase/buf/buf0flu.cc']['before_sha256']
                result = command(['patch', '--batch', '--forward', '--fuzz=0', '-p1',
                                  '-i', str(patch_path)], source)
                result.update(stage=relative, status='DIAGNOSTIC_ONLY',
                              patch_sha256=digest(patch_path))
                records.append(result)
        prepared = load_module('prepared_source_patch', root)
        attempt('unchanged-prepared-function-oracles',
                lambda: prepared.check_functions(source, root, 'after'), records)
        for module, function in [('guest_init_hooks', 'instrument'), ('guest_auth_hooks', 'prepare')]:
            instance = load_module(module, root)
            attempt(module, lambda m=instance, f=function: getattr(m, f)(source), records)
        routine = load_module('routine_schema', root)
        attempt('routine_schema', lambda: routine.prepare(source, root=root), records)
        rejects = {}
        for path in source.rglob('*.rej'):
            relative = str(path.relative_to(source))
            rejects[relative] = path.read_text()
        results[name] = {'source_commit': sha, 'records': records, 'rejects': rejects,
                         'wall_seconds': time.monotonic() - started,
                         'qualification': 'NOT_PREPARED_NOT_BUILT_NOT_ACCEPTED'}
        save('trial-adapted.json' if adapted else 'trial-results.json', results)
        selected = SCRATCH / ('selected-' + name)
        for relative in ('sql/sql_prepare.cc', 'storage/innobase/log/log0log.cc',
                         'storage/innobase/buf/buf0flu.cc'):
            path = selected / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, path)
        storage.append(guard.check())
        shutil.rmtree(source_parent)
        shutil.rmtree(root)
    save('storage-samples.json', storage)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('fetch', 'trial'))
    parser.add_argument('--adapted', action='store_true')
    args = parser.parse_args()
    EVIDENCE.mkdir(exist_ok=True)
    SCRATCH.mkdir(exist_ok=True)
    fetch() if args.operation == 'fetch' else trial(args.adapted)
