#!/usr/bin/env python3
"""Preserve knowledge, not workspace state; recreatable output is disposable."""
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
POLICY = 'cleanup-policy.json'
KEEP_KINDS = {'unique-source', 'unpushed-history', 'active-task', 'unique-results',
              'durable-evidence', 'active-release'}


class UniqueInformation(ValueError):
    def __init__(self, code, reason, path):
        self.code, self.reason, self.path = code, reason, str(path)
        super().__init__(f'{code}: {reason}: {path}')


def policy_for(path):
    file = safe_path(path / POLICY)
    if not file.exists():
        return {'reproducible': {}, 'keep': {}}
    data = json.loads(file.read_text())
    if not isinstance(data, dict):
        raise ValueError('cleanup policy must be an object')
    for section in ('reproducible', 'keep'):
        entries = data.setdefault(section, {})
        if not isinstance(entries, dict):
            raise ValueError('cleanup policy section must be an object: ' + section)
        for relative, item in entries.items():
            if Path(relative).is_absolute() or '..' in Path(relative).parts:
                raise ValueError('policy path must stay inside workspace')
            safe_path(path / relative)
            if not isinstance(item, dict) or not isinstance(item.get('reason'), str) or not item['reason'].strip():
                raise ValueError('policy entry requires a specific reason: ' + relative)
            if section == 'keep' and (item.get('kind') not in KEEP_KINDS or item['reason'].strip().lower() in
                                       {'cache', 'expensive to rebuild', 'maybe useful', 'unclear',
                                        'downloading again is inconvenient', 'might be useful later'}):
                raise ValueError('KEEP requires unique value or active ownership, not cache cost')
            if section == 'reproducible' and not all(isinstance(item.get(k), str) and item[k].strip()
                                                       for k in ('command', 'inputs')):
                raise ValueError('reproducible entry requires command and source/input identities')
    return data


def holds_disposable(path, policy):
    # Evidence justification must not protect unrelated build residue.
    return any((path / relative).is_relative_to(path / area) or
               (path / area).is_relative_to(path / relative)
               for relative in policy['keep'] for area in ('temp', 'worktree'))


def reproduced(source, path, policy):
    return any(source.is_relative_to(path / relative) for relative in policy['reproducible'])


def inspect_nested_git(directory, repo):
    # A checkout is not evidence by itself. Protect actual source/history changes.
    if Path(git(directory, 'rev-parse', '--show-toplevel').strip()) != directory:
        raise ValueError('invalid nested Git marker; inspect ownership before cleanup: ' + str(directory))
    changed = git(directory, 'status', '--porcelain', '--untracked-files=all')
    if changed:
        raise UniqueInformation('unique_source', 'nested Git checkout has uncommitted files', directory)
    commits = set(git(directory, 'rev-list', '--all').splitlines())
    retained = set(git(repo, 'rev-list', '--all').splitlines())
    if commits - retained:
        raise UniqueInformation('unpreserved_history',
                                'nested commits need a retained ref/bundle or verified remote preservation', directory)


def large_retained(root):
    """One traversal; report both files and directories over 1 GiB."""
    sizes = {}
    for parent, dirs, files in os.walk(root, topdown=False, followlinks=False):
        parent = Path(parent)
        total = 0
        for name in files:
            f = parent / name
            if not f.is_symlink():
                size = allocated_bytes(f)
                sizes[f] = size
                total += size
        total += sum(sizes.get(parent / name, 0) for name in dirs)
        sizes[parent] = total
    return [(p, size) for p, size in sizes.items() if size > 1 << 30]


def retention_report(path, policy=None):
    policy = policy_for(path) if policy is None else policy
    rows = []
    for retained, size in large_retained(path):
        item = policy['keep'].get(str(retained.relative_to(path)))
        rows.append({'path': str(retained), 'bytes': size, 'justified': bool(item),
                     'keep_kind': item['kind'] if item else None,
                     'keep_reason': item['reason'] if item else None})
    return rows


def retention_debt(path, policy=None):
    # Each large path needs its own explanation; a parent cannot hide a cache child.
    return [{'path': row['path'], 'bytes': row['bytes'], 'code': 'unjustified_retention',
             'reason': '>1 GiB retained without a specific KEEP kind/reason'}
            for row in retention_report(path, policy) if not row['justified']]


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
    if path == repo or path in repo.parents:
        raise ValueError('refusing repository source root')
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
                    print(('REVIEW: ' if isinstance(exc, UniqueInformation) else 'INSPECTION ERROR: ') + str(exc), flush=True)


def retained_objects(repo):
    return {line.split()[0] for line in git(repo, 'rev-list', '--objects', '--all').splitlines()}


def already_committed(source, repo, objects):
    return git(repo, 'hash-object', str(source)).strip() in objects


def scratch_evidence(origin, path, repo, tracked=()):
    """Inspect actual files; preserve small unique knowledge, not entire trees."""
    policy = policy_for(path)
    sources = []
    tracked = set(tracked)
    objects = retained_objects(repo)
    for parent, dirs, files in os.walk(origin, followlinks=False):
        parent = Path(parent)
        if parent != origin and ('.git' in dirs or '.git' in files):
            inspect_nested_git(parent, repo)
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', '.pytest_cache'}
                   and not (parent / d).is_symlink()]
        for name in files:
            source = parent / name
            if name == '.git' or source.is_symlink():
                continue  # Never follow a linked target; the disposable link itself is removed.
            if str(source.relative_to(origin)) in tracked:
                continue  # Committed reports/source are already preserved by retained Git refs.
            if reproduced(source, path, policy):
                continue
            if (source.suffix in SOURCE or is_evidence(source)) and already_committed(source, repo, objects):
                continue
            # Small source, evidence and opaque data are copied and hashed before deletion.
            # Compiled outputs/cache blobs are reproductions of source, not result knowledge.
            with source.open('rb') as stream:
                header = stream.read(32)
            cache_key = any(part in CACHES for part in source.relative_to(origin).parts[:-1]) and bool(
                re.fullmatch(r'[0-9a-f]{64}-[ad]', source.name))
            known_output = (source.suffix in {'.o', '.a', '.so', '.dylib', '.wasm', '.pyc'} or cache_key or
                            header.startswith((b'!<arch>\n', b'go object ', b'\x7fELF', b'\xcf\xfa\xed\xfe')))
            if known_output and not is_evidence(source):
                continue
            if source.stat().st_size > 8 * 1024**2:
                if source.suffix not in SOURCE and not is_evidence(source):
                    raise ValueError('inspect opaque data and record a reproduction recipe or preserve it compactly: ' + str(source))
                code = 'unique_source' if source.suffix in SOURCE else 'unique_results'
                raise UniqueInformation(code, 'unrepresented source/result bytes need compact preservation or a reproduction record', source)
            sources.append(source)
    return sources


def validate_temp(path, repo):
    temp = safe_path(path / 'temp')
    for line in git(repo, 'worktree', 'list', '--porcelain').splitlines():
        if line.startswith('worktree ') and Path(line[9:]).is_relative_to(temp):
            raise UniqueInformation('git_ownership', 'registered nested worktree must use Git-aware removal', temp)
    if temp.exists() and ((temp / '.git').exists()):
        inspect_nested_git(temp, repo)
    scratch_evidence(temp, path, repo)
    return temp


def remove_disposable_tree(path):
    """Remove an already-authorized owned tree, including readonly Go cache dirs.

    Ownership/preservation checks belong to the caller. Do not follow symlinks
    or change file permissions outside that tree. Also usable by the CI runner.
    """
    path = Path(path)
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if not path.exists():
        return
    for parent, _, _ in os.walk(path, followlinks=False):
        directory = Path(parent)
        directory.chmod(directory.stat().st_mode | 0o200)
    shutil.rmtree(path)


def discard_temp(path, repo):
    temp = validate_temp(path, repo)
    sources = scratch_evidence(temp, path, repo)
    export_files(path, temp, sources, 'temp')
    if temp.exists():
        remove_disposable_tree(temp)


def check_worktree(path, repo):
    worktree = path / 'worktree'
    if not worktree.exists():
        return None
    safe_path(worktree)
    registered = [line[9:] for line in git(repo, 'worktree', 'list', '--porcelain').splitlines()
                  if line.startswith('worktree ')]
    if str(worktree) not in registered:
        raise ValueError('worktree is not registered; inspect Git ownership before removal')
    if git(worktree, 'status', '--porcelain', '--untracked-files=all'):
        raise UniqueInformation('unique_source', 'worktree has uncommitted files; preserve patch/commit first', worktree)
    branch = git(worktree, 'branch', '--show-current').strip()
    sha = git(worktree, 'rev-parse', 'HEAD').strip()
    if not branch or git(repo, 'rev-parse', 'refs/heads/' + branch).strip() != sha:
        raise UniqueInformation('unpreserved_history', 'worktree HEAD lacks a retained branch ref', worktree)
    return {'branch': branch, 'sha': sha}


def is_evidence(source):
    return source.suffix in EVIDENCE or 'sha256' in source.name.lower() or 'checksum' in source.name.lower()


def worktree_evidence(path):
    worktree = path / 'worktree'
    if not worktree.exists():
        return []
    record = json.loads((path / RECEIPT).read_text())
    repo = Path(record['repo'])
    tracked = git(worktree, 'ls-files', '-z').split('\0')
    return scratch_evidence(worktree, path, repo, tracked)


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


def assessment(path, repo):
    """Policy classification is separate from permission to delete arbitrary paths."""
    path = safe_path(path)
    def result(kind, code, reason, automatic=False):
        return {'path': str(path), 'classification': kind, 'code': code,
                'reason': reason, 'automatic': automatic}
    if path.name == POLICY and path.is_file():
        policy_for(path.parent)
        return result('KEEP', 'durable_evidence', 'reproduction/retention declarations')
    if path.is_file() and path.is_relative_to(repo):
        tracked = git(repo, 'ls-files', '-z').split('\0')
        if str(path.relative_to(repo)) in tracked:
            return result('KEEP', 'committed_product_source', 'tracked product source/metadata stays in its checkout')
    if (path.name in CACHES or path.name == 'mariamem-cache') and not (path / RECEIPT).is_file():
        policy = policy_for(path)
        if '.' in policy['keep']:
            return result('KEEP', 'explicit_retention', json.dumps(policy['keep'], sort_keys=True))
        return result('DELETE', 'recreatable_cache',
                      'cache is disposable after its users finish; verify ownership/activity before manual removal')
    if not (path / RECEIPT).is_file():
        if path.is_dir():
            policy = policy_for(path)
            if holds_disposable(path, policy):
                return result('KEEP', 'explicit_retention', json.dumps(policy['keep'], sort_keys=True))
            # Inspect for concrete unique information instead of using an unknown-directory REVIEW.
            if (path / '.git').exists():
                try:
                    inspect_nested_git(path, repo)
                except UniqueInformation as exc:
                    return result('REVIEW', exc.code, str(exc))
            objects = retained_objects(repo)
            for parent, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__'} and not (Path(parent) / d).is_symlink()]
                for name in files:
                    f = Path(parent) / name
                    if f.is_symlink() or name == POLICY or reproduced(f, path, policy):
                        continue
                    if f.suffix in SOURCE or is_evidence(f):
                        if already_committed(f, repo, objects):
                            continue
                        return result('REVIEW', 'unique_source_or_results',
                                      'unarchived source/result file identified: ' + str(f))
        return result('DELETE', 'recreatable_candidate',
                      'no unique source/result identified; unmanaged deletion requires ownership/recipe inspection')
    record = load(path, repo)  # Malformed receipts/path errors are inspection errors, never REVIEW excuses.
    if record.get('shutdown_unconfirmed'):
        return result('REVIEW', 'active_ownership',
                      'recorded child-group shutdown unconfirmed; inspect processes then finalize')
    if record['state'] == 'cleaned' and not any((path / name).exists() for name in ('temp', 'worktree')):
        return result('KEEP', 'durable_evidence', 'completed receipt and compact archived results')
    if record['state'] not in {'completed', 'failed', 'cleaned'}:
        return result('KEEP', 'active_task', 'recorded prepared/running experiment: ' + record['name'])
    try:
        with exclusive(path):
            policy = policy_for(path)
            if holds_disposable(path, policy):
                return result('KEEP', 'explicit_retention', json.dumps(policy['keep'], sort_keys=True))
            check_worktree(path, repo)
            validate_temp(path, repo)
            safe_path(path / 'evidence')
            worktree_evidence(path)
    except UniqueInformation as exc:
        return result('REVIEW', exc.code, str(exc))
    except ValueError as exc:
        if 'active/locked' not in str(exc):
            raise
        return result('KEEP', 'active_task', str(exc))
    return result('DELETE', 'completed_recreatable_state',
                  'completed owned scratch/worktree; compact knowledge exported before removal', True)


def classify(path, repo):
    decision = assessment(path, repo)
    return decision['classification'], decision['code'] + ': ' + decision['reason']


def cleanup(path, repo):
    with exclusive(path):
        record = load(path, repo)
        if record.get('shutdown_unconfirmed'):
            raise ValueError('child shutdown unconfirmed; verify inactivity before finalize')
        if record['state'] not in {'completed', 'failed', 'cleaned'}:
            raise ValueError('only completed/failed experiments can be cleaned')
        if holds_disposable(path, policy_for(path)):
            raise ValueError('explicit KEEP must be resolved before deleting its workspace')
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
    clean.add_argument('--json', action='store_true', help='machine-readable classifications and cleanup debt')
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
            decisions = []
            before = allocated_bytes(root)
            for path in paths:
                decision = assessment(path, repo)
                decision['bytes'] = allocated_bytes(path)
                decisions.append(decision)
                if not args.json:
                    print(f"{decision['classification']:6} {decision['bytes']/(1<<30):.3f} GiB {path.name}: "
                          f"{decision['code']}: {decision['reason']}", flush=True)
                if args.apply and decision['classification'] == 'DELETE' and decision['automatic']:
                    cleanup(path, repo)
            debt, retained = [], []
            if args.apply:
                for path in paths:
                    if path.is_dir():
                        retained.extend(retention_report(path))
                    elif allocated_bytes(path) > 1 << 30:
                        item = policy_for(root)['keep'].get(path.name)
                        retained.append({'path': str(path), 'bytes': allocated_bytes(path),
                                         'justified': bool(item), 'keep_kind': item['kind'] if item else None,
                                         'keep_reason': item['reason'] if item else None})
                if not args.name and allocated_bytes(root) > 1 << 30:
                    item = policy_for(root)['keep'].get('.')
                    retained.append({'path': str(root), 'bytes': allocated_bytes(root),
                                     'justified': bool(item), 'keep_kind': item['kind'] if item else None,
                                     'keep_reason': item['reason'] if item else None})
                debt = [{'path': row['path'], 'bytes': row['bytes'], 'code': 'unjustified_retention',
                         'reason': '>1 GiB retained without a specific KEEP kind/reason'}
                        for row in retained if not row['justified']]
            summary = {'before_bytes': before, 'after_bytes': allocated_bytes(root),
                       'applied': args.apply, 'decisions': decisions,
                       'retained_large_paths': retained, 'cleanup_debt': debt}
            if args.json:
                print(json.dumps(summary, indent=2))
            else:
                print('APPLY: compact evidence retained; unmanaged DELETE candidates need manual ownership checks'
                      if args.apply else 'DRY RUN: no files removed')
                print(f"Disk: {before/(1<<30):.3f} → {summary['after_bytes']/(1<<30):.3f} GiB")
                for item in retained:
                    print('RETAINED >1 GiB: ' + json.dumps(item))
                for item in debt:
                    print('CLEANUP DEBT: ' + json.dumps(item))
            if debt:
                return 2
        return 0
    except (ValueError, OSError, DiskLimit, subprocess.CalledProcessError) as exc:
        print(json.dumps({'error': str(exc), 'code': 'inspection_error'}) if getattr(args, 'json', False) else str(exc), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
