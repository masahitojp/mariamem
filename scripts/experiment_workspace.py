#!/usr/bin/env python3
"""Own disposable experiment scratch; unknown legacy paths stay REVIEW."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from experiment_disk import DiskGuard, DiskLimit, ProcessStopError, allocated_bytes, run_guarded

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'mariamem-experiment-v1'
RECEIPT = 'experiment.json'
CACHES = {'cache', 'gocache', 'gomodcache', 'mod-cache', 'downloads', 'tools',
          'toolchain', 'node_modules', '.venv', 'venv'}
EVIDENCE = {'.md', '.json', '.jsonl', '.csv', '.tsv', '.log', '.txt', '.pprof', '.heap',
            '.prof', '.profile', '.sha256', '.sha512', '.gz'}
SOURCE = {'.go', '.py', '.sh', '.c', '.cpp', '.h', '.inc', '.patch', '.s'}


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_path(path):
    path = Path(os.path.abspath(path))
    if path.resolve() != path or path.is_symlink():
        raise ValueError('refusing symlink path/ancestor: ' + str(path))
    return path


def root_path(path, repo):
    path = safe_path(path)
    if path == repo or path in repo.parents or 'mariamem-cache' in path.parts:
        raise ValueError('refusing source/cache root')
    if path.is_relative_to(repo) and not path.is_relative_to(repo / 'build'):
        raise ValueError('in-repository scratch must be under ignored build/')
    return path


def named(root, name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', name):
        raise ValueError('name must be a simple directory name, without path separators')
    return safe_path(root / name)


def save(path, record):
    destination = safe_path(path / RECEIPT)
    temporary = safe_path(path / (RECEIPT + '.pending'))
    with temporary.open('x') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
    os.replace(temporary, destination)


def load(path, repo):
    receipt = path / RECEIPT
    if receipt.is_symlink():
        raise ValueError('linked experiment receipt')
    record = json.loads(receipt.read_text())
    if not isinstance(record, dict):
        raise ValueError('unknown experiment receipt')
    if record.get('owner') != OWNER or record.get('repo') != str(repo) or record.get('name') != path.name:
        raise ValueError('unknown experiment owner/repository/name')
    if record.get('state') not in {'prepared', 'running', 'completed', 'failed', 'cleaned'}:
        raise ValueError('unknown experiment state')
    if record.get('evidence') != 'evidence' or record.get('disposable') not in (['temp'], ['temp', 'worktree']):
        raise ValueError('unknown experiment layout')
    return record


@contextlib.contextmanager
def exclusive(path):
    lock = path / '.experiment.lock'
    if lock.is_symlink():
        raise ValueError('linked experiment lock')
    with lock.open('rb') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('experiment is active/locked; leave it intact') from exc
        yield


def prepare(root, name, repo, branch=None, min_free_gib=8, budget_gib=2):
    path = named(root, name)
    if branch and not re.fullmatch(r'experiment/[A-Za-z0-9_-]+', branch):
        raise ValueError('worktree branch must be experiment/<simple-name>')
    DiskGuard(path, min_free_gib, budget_gib).check()
    if path.exists():
        raise ValueError('experiment destination must be fresh')
    path.mkdir(parents=True)
    (path / 'temp').mkdir()
    (path / 'evidence').mkdir()
    (path / '.experiment.lock').touch()
    record = {'owner': OWNER, 'name': name, 'repo': str(repo), 'state': 'prepared',
              'base_sha': git(repo, 'rev-parse', 'HEAD').strip(), 'created': time.time(),
              'min_free_gib': min_free_gib, 'budget_gib': budget_gib,
              'disposable': ['temp'], 'evidence': 'evidence'}
    save(path, record)
    with exclusive(path):
        try:
            if branch:
                exists = subprocess.run(['git', '-C', str(repo), 'show-ref', '--verify', '--quiet',
                                         'refs/heads/' + branch]).returncode == 0
                args = ['worktree', 'add'] + ([] if exists else ['-b', branch])
                git(repo, *args, str(path / 'worktree'), branch if exists else 'HEAD')
                record['branch'] = branch
                record['disposable'].append('worktree')
                save(path, record)
            DiskGuard(path, min_free_gib, budget_gib).check()
        except BaseException:
            record['state'] = 'failed'
            save(path, record)
            # Retain any checkout/evidence for inspection; only owned scratch is discarded.
            discard_temp(path, repo)
            raise
    return path


def execute(path, repo, command, timeout=900):
    with exclusive(path):
        record = load(path, repo)
        if record['state'] != 'prepared':
            raise ValueError('run requires a fresh prepared workspace')
        temp = safe_path(path / 'temp')
        evidence = safe_path(path / 'evidence')
        for name in ('tmp', 'go-tmp'):
            (temp / name).mkdir()
        env = dict(os.environ, TMPDIR=str(temp / 'tmp'), GOTMPDIR=str(temp / 'go-tmp'),
                   MARIAMEM_EXPERIMENT_TEMP=str(temp), MARIAMEM_EXPERIMENT_EVIDENCE=str(evidence))
        guard = DiskGuard(path, record['min_free_gib'], record['budget_gib'])
        record.update(state='running', command=command)
        save(path, record)
        code = 2
        try:
            with (evidence / 'console.log').open('xb') as output:
                code = run_guarded(command, guard, cwd=path / 'worktree' if (path / 'worktree').exists() else temp,
                                   env=env, output=output, timeout=timeout)
            return code
        except (DiskLimit, KeyboardInterrupt, OSError, ValueError) as exc:
            record['error'] = str(exc)
            if isinstance(exc, ProcessStopError):
                record['shutdown_unconfirmed'] = True
            print(str(exc), flush=True)
            return 2
        finally:
            record.update(state='completed' if code == 0 else 'failed', returncode=code,
                          peak_owned_bytes=guard.peak, minimum_free_bytes=guard.minimum_free)
            save(path, record)
            if code != 0 and not record.get('shutdown_unconfirmed'):
                try:
                    discard_temp(path, repo)
                except ValueError as exc:
                    print('REVIEW: failed scratch retained: ' + str(exc), flush=True)


def validate_temp(path, repo):
    temp = safe_path(path / 'temp')
    for line in git(repo, 'worktree', 'list', '--porcelain').splitlines():
        if line.startswith('worktree ') and Path(line[9:]).is_relative_to(temp):
            raise ValueError('registered worktree inside temp; use Git cleanup manually')
    for parent, dirs, files in os.walk(temp, followlinks=False):
        if '.git' in dirs or '.git' in files or any(d in CACHES for d in dirs):
            raise ValueError('source/cache inside temp requires manual preservation: ' + parent)
        dirs[:] = [d for d in dirs if not (Path(parent) / d).is_symlink()]
        for name in files:
            source = Path(parent) / name
            if is_evidence(source) and not source.is_symlink() and source.stat().st_size > 8 * 1024**2:
                raise ValueError('large temp evidence requires manual preservation: ' + str(source))
    return temp


def discard_temp(path, repo):
    temp = validate_temp(path, repo)
    sources = [Path(parent) / name for parent, _, files in os.walk(temp, followlinks=False)
               for name in files if is_evidence(Path(parent) / name) and not (Path(parent) / name).is_symlink()]
    export_files(path, temp, sources, 'temp')
    if temp.exists():
        shutil.rmtree(temp)


def check_worktree(path, repo):
    worktree = path / 'worktree'
    if not worktree.exists():
        return None
    safe_path(worktree)
    registered = [line[9:] for line in git(repo, 'worktree', 'list', '--porcelain').splitlines()
                  if line.startswith('worktree ')]
    if str(worktree) not in registered or git(worktree, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('worktree is unregistered or dirty; commit/preserve source before cleanup')
    branch = git(worktree, 'branch', '--show-current').strip()
    sha = git(worktree, 'rev-parse', 'HEAD').strip()
    if not branch or git(repo, 'rev-parse', 'refs/heads/' + branch).strip() != sha:
        raise ValueError('worktree source lacks a retained local branch ref')
    return {'branch': branch, 'sha': sha}


def is_evidence(source):
    return source.suffix in EVIDENCE or 'sha256' in source.name.lower() or 'checksum' in source.name.lower()


def worktree_evidence(path):
    """Read-only assessment before any removal or evidence export."""
    worktree = path / 'worktree'
    sources = []
    if not worktree.exists():
        return sources
    tracked = set(git(worktree, 'ls-files', '-z').split('\0'))
    for parent, dirs, files in os.walk(worktree, followlinks=False):
        parent = Path(parent)
        for d in dirs:
            if d == '.git':
                raise ValueError('nested Git checkout requires manual preservation')
            if (parent / d).is_symlink():
                raise ValueError('linked worktree directory requires manual preservation')
            if d in CACHES and not (parent / d).is_symlink():
                raise ValueError('nested cache requires manual preservation: ' + str(parent / d))
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', '.pytest_cache'}
                   and not (parent / d).is_symlink()]
        for name in files:
            source = parent / name
            if source.is_symlink():
                raise ValueError('linked worktree file requires manual preservation')
            if name == '.git':
                continue
            rel = source.relative_to(worktree)
            evidence = is_evidence(source)
            ignored_source = source.suffix in SOURCE and rel.parts[0] == 'build'
            if not evidence and not ignored_source:
                if str(rel) not in tracked:
                    raise ValueError('unknown ignored output requires manual review: ' + str(source))
                continue
            if source.stat().st_size > 8 * 1024**2:
                raise ValueError('large evidence/source needs manual preservation: ' + str(source))
            sources.append(source)
    return sources


def export_files(path, origin, sources, category):
    """Keep compact evidence without overwriting a distinct earlier result."""
    archive = safe_path(path / 'evidence' / category)
    records = []
    for source in sources:
        rel = source.relative_to(origin)
        target = safe_path(archive / rel)
        sha = digest(source)
        if target.exists() and digest(target) != sha:
            raise ValueError('distinct evidence already exists: ' + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
        if digest(target) != sha:
            raise ValueError('evidence copy failed verification')
        records.append({'path': str(rel), 'bytes': source.stat().st_size, 'sha256': sha})
    checksum = safe_path(path / 'evidence' / (category + '-checksums.json'))
    if records or not checksum.exists():
        checksum.write_text(json.dumps(records, indent=2) + '\n')
    return records


def archive_worktree(path):
    return export_files(path, path / 'worktree', worktree_evidence(path), 'worktree')


def classify(path, repo):
    if path.name in CACHES or path.name == 'mariamem-cache':
        return 'CACHE', 'shared input; never selected'
    if not path.is_dir() or path.is_symlink() or not (path / RECEIPT).is_file():
        return 'REVIEW', 'unmanaged path; not auto-deleted'
    try:
        record = load(safe_path(path), repo)
        if record.get('shutdown_unconfirmed'):
            return 'REVIEW', 'child shutdown unconfirmed; verify inactivity before finalize'
        if record['state'] == 'cleaned':
            return 'EVIDENCE', 'completed receipt/archive retained'
        if record['state'] not in {'completed', 'failed'}:
            return 'KEEP', 'prepared/running; finalize when no longer active'
        with exclusive(path):
            check_worktree(path, repo)
            validate_temp(path, repo)
            safe_path(path / 'evidence')
            worktree_evidence(path)
        return 'DISPOSABLE', 'owned completed scratch/worktree; evidence retained'
    except (ValueError, OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        return 'REVIEW', str(exc)


def cleanup(path, repo):
    with exclusive(path):
        record = load(path, repo)
        if record.get('shutdown_unconfirmed'):
            raise ValueError('child shutdown unconfirmed; verify inactivity before finalize')
        if record['state'] not in {'completed', 'failed'}:
            raise ValueError('only completed/failed experiments can be cleaned')
        info = check_worktree(path, repo)
        validate_temp(path, repo)
        safe_path(path / 'evidence')
        archived = archive_worktree(path)
        if info:
            record['source'] = info
            save(path, record)
            if check_worktree(path, repo) != info:
                raise ValueError('worktree identity changed during export')
            git(repo, 'worktree', 'remove', str(path / 'worktree'))  # Never --force.
        discard_temp(path, repo)
        record.update(state='cleaned', source=info or record.get('source'),
                      archived_files=max(len(archived), record.get('archived_files', 0)), cleaned=time.time())
        save(path, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT / 'build/experiment-work')
    parser.add_argument('--repo', type=Path, default=ROOT)
    commands = parser.add_subparsers(dest='action', required=True)
    new = commands.add_parser('prepare')
    new.add_argument('name')
    new.add_argument('--branch')
    new.add_argument('--min-free-gib', type=float, default=8)
    new.add_argument('--budget-gib', type=float, default=2)
    run = commands.add_parser('run')
    run.add_argument('name')
    run.add_argument('--timeout', type=float, default=900)
    run.add_argument('command', nargs=argparse.REMAINDER)
    finish = commands.add_parser('finalize', help='mark manually supervised work completed; does not approve product changes')
    finish.add_argument('name')
    clean = commands.add_parser('cleanup')
    clean.add_argument('--name')
    clean.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        repo = safe_path(args.repo)
        root = root_path(args.root, repo)
        if args.action == 'prepare':
            print(prepare(root, args.name, repo, args.branch, args.min_free_gib, args.budget_gib))
        elif args.action == 'run':
            command = args.command[1:] if args.command[:1] == ['--'] else args.command
            return execute(named(root, args.name), repo, command, args.timeout)
        elif args.action == 'finalize':
            path = named(root, args.name)
            with exclusive(path):
                record = load(path, repo)
                if record['state'] == 'cleaned':
                    raise ValueError('already cleaned')
                record['state'] = 'completed'
                record.pop('shutdown_unconfirmed', None)
                save(path, record)
        else:
            paths = [named(root, args.name)] if args.name else sorted(root.iterdir()) if root.exists() else []
            print(f'Disk usage: {allocated_bytes(root)/(1<<30):.3f} GiB owned under {root}')
            for path in paths:
                kind, reason = classify(path, repo)
                print(f'{kind:10} {allocated_bytes(path)/(1<<30):.3f} GiB {path.name}: {reason}', flush=True)
                if args.apply and kind == 'DISPOSABLE':
                    cleanup(path, repo)
            print('APPLY complete; evidence/caches/REVIEW retained' if args.apply else 'DRY RUN: no files removed')
            if args.apply:
                print(f'After cleanup: {allocated_bytes(root)/(1<<30):.3f} GiB retained')
        return 0
    except (ValueError, OSError, DiskLimit, subprocess.CalledProcessError) as exc:
        print(str(exc), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
