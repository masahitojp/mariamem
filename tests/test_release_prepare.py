"""Exercise the release skill's mechanics with all Git/GitHub boundaries mocked."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_prepare as release

TAG = 'v0.1.0-alpha.5'
SHA = 'a' * 40


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    version = tmp_path / 'python/mariamem/_version.py'
    version.parent.mkdir(parents=True)
    version.write_text('GIT_TAG="v0.1.0-alpha.5"\nSTAGE="alpha"\nSERIAL=5\n')
    notes = tmp_path / 'release/NOTES-alpha.5.md'
    notes.parent.mkdir()
    notes.write_text('# mariamem ' + TAG)
    calls = []
    def run(args, root):
        calls.append(args)
        if args[:3] == ['git', 'branch', '--show-current']:
            return 'main'
        if args[:3] == ['git', 'remote', 'get-url']:
            return 'git@github.com:masahitojp/mariamem.git'
        if args[:2] == ['gh', 'api']:
            return '[[]]'
        if args == ['git', 'diff', '--name-only', '--no-renames']:
            return 'python/mariamem/_version.py\nrelease/NOTES-alpha.5.md'
        if args == ['git', 'rev-parse', 'HEAD']:
            return SHA
        if args == ['git', 'ls-remote', 'origin', 'refs/heads/main']:
            return SHA + '\trefs/heads/main'
        if args[:3] == ['gh', 'workflow', 'run']:
            return 'https://github.com/masahitojp/mariamem/actions/runs/123'
        return ''
    monkeypatch.setattr(release, 'run', run)
    return tmp_path, calls, run


def test_missing_version_rejected():
    script = Path(release.__file__)
    result = subprocess.run([sys.executable, str(script), 'preflight'], capture_output=True, text=True)
    assert result.returncode != 0 and 'version' in result.stderr


@pytest.mark.parametrize('value', ['', 'alpha.5', 'v0.1.0', 'v0.1.0-alpha.0', 'v01.1.0-alpha.5', 'v0.1.0-dev.5'])
def test_invalid_version_no_git_operations(prepared, value):
    root, calls, _ = prepared
    with pytest.raises(ValueError):
        release.preflight(root, value)
    assert calls == []


@pytest.mark.parametrize('kind', ['local-tag', 'remote-tag', 'release', 'dirty', 'branch', 'remote'])
def test_unsafe_preconditions_stop(prepared, monkeypatch, kind):
    root, calls, original = prepared
    def run(args, directory):
        if kind == 'local-tag' and args[:2] == ['git', 'tag']:
            return TAG
        if kind == 'remote-tag' and args[:3] == ['git', 'ls-remote', '--tags']:
            return SHA + '\trefs/tags/' + TAG
        if kind == 'release' and args[:2] == ['gh', 'api']:
            return json.dumps([[{'tag_name': TAG}]])
        if kind == 'dirty' and args[:2] == ['git', 'status']:
            return ' M unrelated.go'
        if kind == 'branch' and args[:2] == ['git', 'branch']:
            return 'feature'
        if kind == 'remote' and args[:2] == ['git', 'remote']:
            return 'https://github.com/another/repo.git'
        return original(args, directory)
    monkeypatch.setattr(release, 'run', run)
    with pytest.raises(ValueError):
        release.preflight(root, TAG)
    assert not any(a[:2] == ['git', 'push'] or a[:3] == ['gh', 'workflow', 'run'] for a in calls)


def test_unrelated_changes_never_committed(prepared, monkeypatch):
    root, calls, original = prepared
    def run(args, directory):
        if args == ['git', 'ls-files', '--others', '--exclude-standard']:
            return 'unrelated.py'
        return original(args, directory)
    monkeypatch.setattr(release, 'run', run)
    with pytest.raises(ValueError, match='unexpected'):
        release.submit(root, TAG)
    assert not any(a[:2] == ['git', 'add'] or a[:2] == ['git', 'commit'] for a in calls)


def test_checks_exact_remote_dispatch_and_no_poll(prepared):
    root, calls, _ = prepared
    result = release.submit(root, TAG)
    assert [sys.executable, 'scripts/verify.py', 'check'] in calls
    commit = next(a for a in calls if a[:2] == ['git', 'commit'])
    assert TAG in commit[-1]
    dispatch = next(a for a in calls if a[:3] == ['gh', 'workflow', 'run'])
    assert 'candidate_ref=' + SHA in dispatch and 'operation=release' in dispatch
    assert calls[-1] == dispatch
    assert result['candidate'] == SHA and result['workflow'].endswith('/123')
    assert not any(a[:2] == ['gh', 'run'] for a in calls)


def test_remote_mismatch_never_dispatches(prepared, monkeypatch):
    root, calls, original = prepared
    def run(args, directory):
        if args == ['git', 'ls-remote', 'origin', 'refs/heads/main']:
            return 'b' * 40 + '\trefs/heads/main'
        return original(args, directory)
    monkeypatch.setattr(release, 'run', run)
    with pytest.raises(ValueError, match='remote main'):
        release.submit(root, TAG)
    assert not any(a[:3] == ['gh', 'workflow', 'run'] for a in calls)


def test_failed_checks_never_commit_or_push(prepared, monkeypatch):
    root, calls, original = prepared
    def run(args, directory):
        if args == [sys.executable, 'scripts/verify.py', 'check']:
            raise RuntimeError('checks failed')
        return original(args, directory)
    monkeypatch.setattr(release, 'run', run)
    with pytest.raises(RuntimeError, match='checks failed'):
        release.submit(root, TAG)
    assert not any(a[:2] in (['git', 'commit'], ['git', 'push']) for a in calls)


def test_skill_is_repository_only_source_coverage_unchanged():
    from check_public import public_files
    root = Path(__file__).resolve().parents[1]
    files = {p.relative_to(root).as_posix() for p in public_files(root)}
    assert '.agents/skills/release/SKILL.md' not in files
    assert 'scripts/release_prepare.py' in files
