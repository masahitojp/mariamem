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
    assert workspace.classify(path, repo)[0] == 'DELETE'
    assert {str(p): p.read_bytes() for p in path.rglob('*') if p.is_file()} == before
    unknown = path.parent / 'unknown'
    unknown.mkdir()
    assert workspace.classify(unknown, repo)[0] == 'DELETE'
    assert workspace.classify(path.parent / 'gocache', repo)[0] == 'DELETE'


def test_cleanup_exports_evidence_removes_worktree_retains_branch(repo):
    path = prepared(repo, 'experiment/fixture')
    complete(path, repo)
    (path / 'temp/result.json').write_text('{"ok":true}')
    (path / 'temp/temporary.bin').write_bytes(b'disposable')
    workspace.cleanup(path, repo)
    assert not (path / 'temp').exists()
    assert not (path / 'worktree').exists()
    assert (path / 'evidence/temp/result.json').read_text() == '{"ok":true}'
    assert not (path / 'evidence/worktree/report.md').exists()  # Git already preserves it.
    assert workspace.git(repo, 'rev-parse', 'refs/heads/experiment/fixture').strip()
    assert workspace.classify(path, repo)[0] == 'KEEP'
    records = json.loads((path / 'evidence/temp-checksums.json').read_text())
    record = next(row for row in records if row['path'] == 'result.json')
    assert record['sha256'] == workspace.digest(path / 'evidence/temp/result.json')


@pytest.mark.parametrize('kind', ['dirty', 'large-profile'])
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
        assert workspace.classify(path, repo)[0] == 'KEEP'
    assert (path / 'temp').exists()


def test_symlink_and_invalid_git_are_inspection_errors_not_review(repo):
    path = prepared(repo)
    complete(path, repo)
    (path / 'temp').rmdir()
    (path / 'temp').symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        workspace.classify(path, repo)
    with pytest.raises(ValueError):
        workspace.cleanup(path, repo)
    (path / 'temp').unlink()
    (path / 'temp/.git').mkdir(parents=True)
    with pytest.raises(ValueError, match='Git marker'):
        workspace.classify(path, repo)
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


def test_failed_job_with_nested_cache_discards_scratch(repo):
    path = prepared(repo)
    code = workspace.execute(path, repo, [sys.executable, '-c',
        "import pathlib,sys; pathlib.Path('gocache').mkdir(); sys.exit(7)"])
    assert code == 7
    assert not (path / 'temp/gocache').exists()
    assert workspace.classify(path, repo)[0] == 'DELETE'


def test_unknown_receipt_shape_is_review(repo):
    path = prepared(repo)
    (path / 'experiment.json').write_text('[]')
    with pytest.raises(ValueError, match='receipt'):
        workspace.classify(path, repo)


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


@pytest.mark.parametrize('name', ['gocache', 'gomodcache', 'toolchain', 'mariamem-cache'])
def test_expensive_cache_is_delete_not_keep(repo, name):
    cache = repo / 'build' / name
    cache.mkdir(parents=True)
    (cache / 'compiler.a').write_bytes(b'rebuild is expensive')
    decision = workspace.assessment(cache, repo)
    assert decision['classification'] == 'DELETE'
    assert decision['code'] == 'recreatable_cache'
    assert not decision['automatic']  # Policy is not permission to delete shared active caches.


def test_clean_completed_worktree_and_cache_are_disposed(repo):
    path = prepared(repo, 'experiment/completed')
    complete(path, repo)
    cache = path / 'worktree/build/gocache'
    cache.mkdir(parents=True)
    (cache / 'compile.a').write_bytes(b'recreatable')
    assert workspace.assessment(path, repo)['classification'] == 'DELETE'
    workspace.cleanup(path, repo)
    assert not (path / 'worktree').exists()
    assert workspace.git(repo, 'rev-parse', 'refs/heads/experiment/completed')


def test_generated_tree_with_recipe_is_delete(repo):
    path = prepared(repo)
    complete(path, repo)
    gen = path / 'temp/generated'
    gen.mkdir()
    # A large generated source is not automatically meaningful evidence.
    with (gen / 'guest.go').open('wb') as f:
        f.truncate(9 * 1024**2)
    policy = {'reproducible': {'temp/generated': {'reason': 'generated module from pinned guest',
              'command': 'converter --guest pinned.wasm --output temp/generated', 'inputs': 'guest sha256:fixture'}}}
    (path / workspace.POLICY).write_text(json.dumps(policy))
    assert workspace.classify(path, repo)[0] == 'DELETE'
    workspace.cleanup(path, repo)
    assert not gen.exists()
    assert (path / workspace.POLICY).exists()


def test_unknown_but_recreatable_directory_not_review(repo):
    unknown = repo / 'build/unfamiliar'
    unknown.mkdir(parents=True)
    (unknown / 'build.o').write_bytes(b'object')
    assert workspace.classify(unknown, repo)[0] == 'DELETE'
    (unknown / 'generated.go').write_text('generated fixture')
    (unknown / workspace.POLICY).write_text(json.dumps({'reproducible': {'.': {
        'reason': 'inspected generated module', 'command': 'converter fixture', 'inputs': 'source SHA:fixture'}}}))
    assert workspace.classify(unknown, repo)[0] == 'DELETE'


def test_review_identifies_actual_unique_source_and_next_action(repo):
    path = prepared(repo, 'experiment/unique')
    complete(path, repo)
    unique = path / 'worktree/report.md'
    unique.write_text('only copy of user changes')
    decision = workspace.assessment(path, repo)
    assert decision['classification'] == 'REVIEW'
    assert decision['code'] == 'unique_source'
    assert 'patch/commit' in decision['reason']
    with pytest.raises(workspace.UniqueInformation):
        workspace.cleanup(path, repo)
    assert unique.read_text() == 'only copy of user changes'


def test_unpushed_commit_survives_completed_worktree_cleanup(repo):
    path = prepared(repo, 'experiment/unpushed')
    (path / 'worktree/new.go').write_text('package fixture')
    workspace.git(path / 'worktree', 'add', 'new.go')
    workspace.git(path / 'worktree', 'commit', '-qm', 'unique local history')
    sha = workspace.git(path / 'worktree', 'rev-parse', 'HEAD').strip()
    complete(path, repo)
    workspace.cleanup(path, repo)
    assert workspace.git(repo, 'rev-parse', 'refs/heads/experiment/unpushed').strip() == sha
    assert workspace.git(repo, 'show', sha + ':new.go') == 'package fixture'


def test_prepared_active_state_is_keep(repo):
    path = prepared(repo)
    decision = workspace.assessment(path, repo)
    assert decision['classification'] == 'KEEP'
    assert decision['code'] == 'active_task'
    with pytest.raises(ValueError, match='completed/failed'):
        workspace.cleanup(path, repo)


def test_small_unique_result_and_opaque_data_exported_before_delete(repo):
    path = prepared(repo)
    complete(path, repo)
    original = path / 'temp/observations.raw'
    original.write_bytes(b'only measurement copy')
    workspace.cleanup(path, repo)
    assert (path / 'evidence/temp/observations.raw').read_bytes() == b'only measurement copy'
    records = json.loads((path / 'evidence/temp-checksums.json').read_text())
    assert records[0]['sha256'] == workspace.digest(path / 'evidence/temp/observations.raw')


def test_retained_over_gib_requires_explicit_unique_value(repo, monkeypatch):
    path = prepared(repo)
    data = path / 'evidence/result.csv'
    data.write_text('canonical trials')
    monkeypatch.setattr(workspace, 'allocated_bytes', lambda p: 2 << 30 if p == data else 0)
    debt = workspace.retention_debt(path)
    assert {x['path'] for x in debt} == {str(data), str(data.parent), str(path)}
    keep = {str(p.relative_to(path)): {'kind': 'unique-results',
            'reason': 'canonical per-trial samples needed to reproduce attribution; reduction loses observations'}
            for p in [data, data.parent, path]}
    (path / workspace.POLICY).write_text(json.dumps({'keep': keep}))
    assert not workspace.retention_debt(path)
    keep['.']['kind'] = 'cache'
    (path / workspace.POLICY).write_text(json.dumps({'keep': keep}))
    with pytest.raises(ValueError, match='KEEP'):
        workspace.retention_debt(path)


def test_evidence_keep_reason_does_not_keep_recreatable_temp(repo):
    path = prepared(repo)
    complete(path, repo)
    (path / 'temp/object.o').write_bytes(b'build output')
    (path / workspace.POLICY).write_text(json.dumps({'keep': {'evidence': {
        'kind': 'durable-evidence', 'reason': 'canonical report and selected trial profiles'}}}))
    assert workspace.classify(path, repo)[0] == 'DELETE'
    workspace.cleanup(path, repo)
    assert not (path / 'temp').exists()


def test_invalid_keep_and_reproduction_records_rejected(repo):
    path = prepared(repo)
    for policy in [{'keep': {'.': {'kind': 'cache', 'reason': 'expensive'}}},
                   {'keep': {'.': {'kind': 'unique-results', 'reason': ''}}},
                   {'keep': {'.': {'kind': 'durable-evidence', 'reason': 'expensive to rebuild'}}},
                   {'reproducible': {'temp': {'reason': 'maybe rebuild'}}},
                   {'keep': {'../other': {'kind': 'active-task', 'reason': 'other task'}}}]:
        (path / workspace.POLICY).write_text(json.dumps(policy))
        with pytest.raises(ValueError):
            workspace.policy_for(path)



def test_copied_committed_source_is_not_unique_review(repo):
    unknown = repo / 'build/copied'
    unknown.mkdir(parents=True)
    (unknown / 'report.md').write_text((repo / 'report.md').read_text())
    assert workspace.classify(unknown, repo)[0] == 'DELETE'


def test_arbitrary_binary_result_is_preserved_not_deleted_by_suffix(repo):
    path = prepared(repo)
    complete(path, repo)
    (path / 'temp/result.bin').write_bytes(b'only measurement bytes')
    workspace.cleanup(path, repo)
    assert (path / 'evidence/temp/result.bin').read_bytes() == b'only measurement bytes'


def test_large_unknown_is_inspection_action_not_unique_review(repo):
    path = prepared(repo)
    complete(path, repo)
    with (path / 'temp/unfamiliar.raw').open('wb') as stream:
        stream.truncate(9 * 1024**2)
    with pytest.raises(ValueError, match='inspect opaque') as error:
        workspace.classify(path, repo)
    assert not isinstance(error.value, workspace.UniqueInformation)
    assert (path / 'temp/unfamiliar.raw').exists()


def test_tracked_build_metadata_is_keep(repo):
    file = repo / 'build/source.txt'
    file.parent.mkdir()
    file.write_text('committed metadata')
    workspace.git(repo, 'add', '-f', 'build/source.txt')
    workspace.git(repo, 'commit', '-qm', 'metadata')
    decision = workspace.assessment(file, repo)
    assert decision['classification'] == 'KEEP'
    assert decision['code'] == 'committed_product_source'



def test_go_cache_blobs_not_archived_as_evidence(repo):
    path = prepared(repo)
    complete(path, repo)
    cache = path / 'temp/gocache'
    cache.mkdir()
    blob = cache / ('a' * 64 + '-d')
    with blob.open('wb') as stream:
        stream.write(b'!<arch>\n')
        stream.truncate(9 * 1024**2)
    assert workspace.classify(path, repo)[0] == 'DELETE'
    workspace.cleanup(path, repo)
    assert not (path / 'evidence/temp/gocache').exists()


def test_unique_data_inside_named_cache_preserved(repo):
    path = prepared(repo)
    complete(path, repo)
    cache = path / 'temp/gocache'
    cache.mkdir()
    (cache / 'user-result.bin').write_bytes(b'unique observations')
    workspace.cleanup(path, repo)
    assert (path / 'evidence/temp/gocache/user-result.bin').read_bytes() == b'unique observations'



def test_cli_large_retention_reports_debt_until_justified(repo, monkeypatch, capsys):
    path = prepared(repo)
    complete(path, repo)
    data = path / 'evidence/results.csv'
    data.write_text('canonical trials')
    monkeypatch.setattr(workspace, 'allocated_bytes', lambda p: 2 << 30 if p == data else 0)
    monkeypatch.setattr(sys, 'argv', ['workspace', '--repo', str(repo), '--root', str(path.parent),
                                    'cleanup', '--name', 'trial', '--apply', '--json'])
    assert workspace.main() == 2
    summary = json.loads(capsys.readouterr().out)
    assert summary['cleanup_debt']
    assert all(row['code'] == 'unjustified_retention' for row in summary['cleanup_debt'])
    assert not (path / 'temp').exists()
    assert data.exists()
    policy = {'keep': {str(p.relative_to(path)): {'kind': 'unique-results',
               'reason': 'canonical sample observations necessary for attribution; reduction loses trials'}
               for p in [path, data.parent, data]}}
    (path / workspace.POLICY).write_text(json.dumps(policy))
    assert workspace.main() == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary['cleanup_debt'] == []
    assert len(summary['retained_large_paths']) == 3
    assert all(row['keep_kind'] == 'unique-results' and row['keep_reason'] for row in summary['retained_large_paths'])


def test_shared_cache_delete_candidate_not_unilaterally_removed(repo, monkeypatch, capsys):
    root = repo / 'build/shared'
    cache = root / 'gocache'
    cache.mkdir(parents=True)
    (cache / 'object.a').write_bytes(b'cached')
    monkeypatch.setattr(sys, 'argv', ['workspace', '--repo', str(repo), '--root', str(root),
                                    'cleanup', '--apply', '--json'])
    assert workspace.main() == 0
    decision = json.loads(capsys.readouterr().out)['decisions'][0]
    assert decision['classification'] == 'DELETE' and not decision['automatic']
    assert cache.exists()



def test_disposable_data_reappearing_after_cleanup_not_kept(repo):
    path = prepared(repo)
    complete(path, repo)
    workspace.cleanup(path, repo)
    (path / 'temp').mkdir()
    (path / 'temp/new.o').write_bytes(b'new output')
    assert workspace.classify(path, repo)[0] == 'DELETE'
    workspace.cleanup(path, repo)
    assert not (path / 'temp').exists()


def test_owned_readonly_cache_cleanup_does_not_follow_external_link(tmp_path):
    external=tmp_path/'external'; external.mkdir()
    (external/'source').write_text('unique external source')
    scratch=tmp_path/'scratch'; scratch.mkdir()
    cache=scratch/'pkg/mod/module@v1'; cache.mkdir(parents=True)
    (cache/'source.go').write_text('recreatable module source')
    (scratch/'external-link').symlink_to(external,target_is_directory=True)
    cache.chmod(0o555); cache.parent.chmod(0o555)
    workspace.remove_disposable_tree(scratch)
    assert not scratch.exists() and (external/'source').read_text()=='unique external source'
