"""Destructive boundaries exercised using tiny isolated Git repositories."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import experiment_disk as disk
import experiment_workspace as workspace


@pytest.fixture
def repo(tmp_path):
    path = tmp_path.resolve() / 'repo'
    path.mkdir()
    for args in [('init', '-q'), ('config', 'user.email', 'test@example.invalid'),
                 ('config', 'user.name', 'Test')]:
        workspace.git(path, *args)
    (path / '.gitignore').write_text('build/\n')
    (path / 'report.md').write_text('committed evidence\n')
    workspace.git(path, 'add', '.')
    workspace.git(path, 'commit', '-qm', 'fixture')
    return path


def prepared(repo, branch=None):
    return workspace.prepare(repo / 'build/work', 'trial', repo, branch,
                             min_free_gib=0.000001, budget_gib=0.1)


def complete(path, repo):
    record = workspace.load(path, repo)
    record['state'] = 'completed'
    workspace.save(path, record)


def test_dry_classification_changes_no_files(repo):
    path = prepared(repo)
    complete(path, repo)
    before = {str(p): p.read_bytes() for p in path.rglob('*') if p.is_file()}
    assert workspace.classify(path, repo)[0] == 'DISPOSABLE'
    assert {str(p): p.read_bytes() for p in path.rglob('*') if p.is_file()} == before
    unknown = path.parent / 'unknown'
    unknown.mkdir()
    assert workspace.classify(unknown, repo)[0] == 'REVIEW'
    assert workspace.classify(path.parent / 'gocache', repo)[0] == 'CACHE'


def test_cleanup_exports_evidence_removes_worktree_retains_branch(repo):
    path = prepared(repo, 'experiment/fixture')
    complete(path, repo)
    (path / 'temp/result.json').write_text('{"ok":true}')
    (path / 'temp/temporary.bin').write_bytes(b'disposable')
    workspace.cleanup(path, repo)
    assert not (path / 'temp').exists()
    assert not (path / 'worktree').exists()
    assert (path / 'evidence/temp/result.json').read_text() == '{"ok":true}'
    assert (path / 'evidence/worktree/report.md').read_text() == 'committed evidence\n'
    assert workspace.git(repo, 'rev-parse', 'refs/heads/experiment/fixture').strip()
    assert workspace.classify(path, repo)[0] == 'EVIDENCE'
    record = json.loads((path / 'evidence/temp-checksums.json').read_text())[0]
    assert record['sha256'] == workspace.digest(path / 'evidence/temp/result.json')


@pytest.mark.parametrize('kind', ['dirty', 'unknown-output', 'cache', 'large-profile'])
def test_uncertain_worktree_is_review(repo, kind):
    path = prepared(repo, 'experiment/fixture')
    complete(path, repo)
    wt = path / 'worktree'
    if kind == 'dirty':
        (wt / 'report.md').write_text('unique change')
    else:
        (wt / 'build').mkdir()
        if kind == 'cache':
            (wt / 'build/gocache').mkdir()
        elif kind == 'large-profile':
            with (wt / 'build/unique.pprof').open('wb') as stream:
                stream.truncate(9 * 1024**2)
        else:
            (wt / 'build/unknown.raw').write_bytes(b'unique')
    assert workspace.classify(path, repo)[0] == 'REVIEW'
    with pytest.raises(ValueError):
        workspace.cleanup(path, repo)
    assert wt.exists()


def test_active_lock_preserves_completed_workspace(repo):
    path = prepared(repo)
    complete(path, repo)
    with (path / '.experiment.lock').open('rb') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert workspace.classify(path, repo)[0] == 'REVIEW'
    assert (path / 'temp').exists()


def test_symlink_and_nested_git_temp_refused(repo):
    path = prepared(repo)
    complete(path, repo)
    (path / 'temp').rmdir()
    (path / 'temp').symlink_to(repo, target_is_directory=True)
    assert workspace.classify(path, repo)[0] == 'REVIEW'
    with pytest.raises(ValueError):
        workspace.cleanup(path, repo)
    (path / 'temp').unlink()
    (path / 'temp/.git').mkdir(parents=True)
    assert workspace.classify(path, repo)[0] == 'REVIEW'
    with pytest.raises(ValueError):
        workspace.cleanup(path, repo)
    assert (repo / 'report.md').exists()


def test_guard_preflight_does_not_spawn(repo, monkeypatch):
    monkeypatch.setattr(disk.shutil, 'disk_usage', lambda _: SimpleNamespace(free=0))
    monkeypatch.setattr(disk.subprocess, 'Popen', lambda *a, **k: pytest.fail('spawned after failed preflight'))
    with pytest.raises(disk.DiskLimit, match='dry-run'):
        disk.run_guarded([sys.executable, '-c', 'pass'], disk.DiskGuard(repo))


def test_guard_stops_budget_overrun(repo):
    owned = repo / 'build/guard'
    owned.mkdir(parents=True)
    command = [sys.executable, '-c', "import pathlib,time; pathlib.Path('huge').write_bytes(b'x'*1048576); time.sleep(10)"]
    with pytest.raises(disk.DiskLimit, match='budget'):
        disk.run_guarded(command, disk.DiskGuard(owned, 0.000001, 0.00001), cwd=owned, interval=0.01)


def test_failure_exports_compact_results_and_discards_temp(repo):
    path = prepared(repo)
    code = workspace.execute(path, repo, [sys.executable, '-c',
        "import pathlib,sys; pathlib.Path('result.csv').write_text('trial,result\\n1,failed\\n'); sys.exit(7)"])
    assert code == 7
    assert workspace.load(path, repo)['state'] == 'failed'
    assert not (path / 'temp').exists()
    assert (path / 'evidence/temp/result.csv').exists()
    assert (path / 'evidence/console.log').exists()


def test_watchdog_and_success_stop_owned_descendants(repo):
    owned = repo / 'build/guard'
    owned.mkdir(parents=True)
    guard = disk.DiskGuard(owned, 0.000001, 0.1)
    with pytest.raises(disk.DiskLimit, match='watchdog'):
        disk.run_guarded([sys.executable, '-c', 'import time; time.sleep(10)'], guard, interval=0.01, timeout=0.05)
    marker = owned / 'escaped'
    child = "import time,pathlib; time.sleep(.4); pathlib.Path('escaped').write_text('bad')"
    parent = 'import subprocess,sys; subprocess.Popen([sys.executable,"-c",' + repr(child) + '])'
    assert disk.run_guarded([sys.executable, '-c', parent], guard, cwd=owned, interval=0.01) == 0
    time.sleep(0.5)
    assert not marker.exists()


def test_guard_refuses_symlinks_and_invalid_thresholds(repo):
    link = repo.parent / 'linked'
    link.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        disk.DiskGuard(link / 'build')
    assert disk.allocated_bytes(link) == 0
    for invalid in [0, -1, float('nan'), float('inf')]:
        with pytest.raises(ValueError):
            disk.DiskGuard(repo, invalid, 1)


def test_receipt_symlink_cannot_overwrite_source(repo):
    path = prepared(repo)
    (path / 'experiment.json.pending').symlink_to(repo / 'report.md')
    with pytest.raises(ValueError, match='symlink'):
        complete(path, repo)
    assert (repo / 'report.md').read_text() == 'committed evidence\n'


def test_failed_job_with_nested_cache_retains_scratch(repo):
    path = prepared(repo)
    code = workspace.execute(path, repo, [sys.executable, '-c',
        "import pathlib,sys; pathlib.Path('gocache').mkdir(); sys.exit(7)"])
    assert code == 7
    assert (path / 'temp/gocache').exists()
    assert workspace.classify(path, repo)[0] == 'REVIEW'


def test_unknown_receipt_shape_is_review(repo):
    path = prepared(repo)
    (path / 'experiment.json').write_text('[]')
    assert workspace.classify(path, repo)[0] == 'REVIEW'


def test_unconfirmed_shutdown_keeps_scratch(repo, monkeypatch):
    path = prepared(repo)
    def denied(process):
        raise PermissionError('simulated child signal denial')
    monkeypatch.setattr(disk, 'stop_group', denied)
    assert workspace.execute(path, repo, [sys.executable, '-c', 'pass']) == 2
    assert workspace.load(path, repo)['shutdown_unconfirmed']
    assert (path / 'temp').exists()
    assert workspace.classify(path, repo)[0] == 'REVIEW'
    with pytest.raises(ValueError, match='shutdown'):
        workspace.cleanup(path, repo)


@pytest.mark.parametrize('state,denied', [('S', True), ('Z', False)])
def test_signal_denial_only_ignored_for_dead_group(monkeypatch, state, denied):
    def reject(*args):
        raise PermissionError('simulated signal denial')
    monkeypatch.setattr(disk.os, 'killpg', reject)
    monkeypatch.setattr(disk.subprocess, 'check_output', lambda *a, **k: '123 ' + state + '\n')
    if denied:
        with pytest.raises(PermissionError):
            disk.signal_group(123, 15)
    else:
        disk.signal_group(123, 15)
