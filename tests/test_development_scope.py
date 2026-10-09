"""Local diff selection cannot depend on historical Product artifact lifetime."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import development_scope as scope
import verify


@pytest.mark.parametrize('path', [
    'README.md', 'docs/development.md', 'docs/reviews/measurement.md',
])
def test_documentation_needs_no_runtime_receipt(path):
    assert scope.select([path])['check_scope'] == 'docs'
    assert not scope.select([path])['integration']


@pytest.mark.parametrize('path', [
    'scripts/experiment_workspace.py', 'scripts/runtime_validation.py',
    'tests/test_runtime_validation.py', '.github/workflows/check.yml',
    '.agents/skills/experiment-workspace/SKILL.md',
])
def test_tooling_remains_checked_without_runtime_qualification(path):
    assert scope.select([path])['check_scope'] == 'python'
    assert not scope.select([path])['integration']


@pytest.mark.parametrize('path', [
    'internal/generatedgo/code/base/owned_prepared.go', 'snapshot.go',
    'python/mariamem/__init__.py', 'python/mariamem/pytest_plugin.py',
    'guest/source.patch', 'guest/inputs.json', 'go.mod',
    'scripts/generate_runtime.py', 'scripts/build_alpha.py',
    'scripts/verify.py', 'tests/test_python_wire.py', 'tests/support/wire_acceptance.py',
    'tests/gointegration/lifecycle_test.go', 'tests/consumer/run_sqlalchemy.py',
    'new-unknown-input.json', 'scripts/new_helper.py', 'tests/test_new_guest_case.py', '../README.md',
])
def test_runtime_and_unknown_changes_do_not_silently_downgrade(path):
    result = scope.select(['docs/development.md', path])
    assert result['check_scope'] == 'full' and result['integration']


def test_missing_or_empty_diff_is_conservative():
    assert scope.select([])['integration']
    assert scope.event_base({'before': 'a'}, 'push') == 'a'
    assert scope.event_base({'pull_request': {'base': {'sha': 'b'}}}, 'pull_request') == 'b'
    assert scope.event_base({}, 'workflow_dispatch') is None


@pytest.fixture
def git_repo(tmp_path):
    root = tmp_path / 'synthetic-git'
    root.mkdir()
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'Test fixture')
    git('config', 'user.email', 'test@example.invalid')
    (root / 'README.md').write_text('old\n')
    git('add', '.')
    git('commit', '-qm', 'baseline')
    base = git('rev-parse', 'HEAD')
    yield root, git, base
    # This nested repository is explicitly test-owned synthetic history, not
    # user source to park indefinitely in workspace cleanup REVIEW.
    shutil.rmtree(root)


def test_event_diff_uses_local_commits_not_receipts_or_network(git_repo, monkeypatch):
    root, git, base = git_repo
    (root / 'release').mkdir()
    (root / 'release/runtime-validation.json').write_text('{"expired":true}')
    (root / 'README.md').write_text('new\n')
    git('add', 'README.md')
    git('commit', '-qm', 'docs')
    candidate = git('rev-parse', 'HEAD')
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    result = scope.plan(root, candidate, base)
    assert result['changed_paths'] == ['README.md']
    assert result['check_scope'] == 'docs' and not result['integration']
    (root / 'release/runtime-validation.json').unlink()
    assert scope.plan(root, candidate, base) == result
    assert scope.plan(root, candidate, '0' * 40)['integration']
    assert scope.plan(root, candidate, 'f' * 40)['integration']
    git('tag', '-a', 'v0.4.4', '-m', 'annotated fixture')
    tag = git('rev-parse', 'v0.4.4')
    with pytest.raises(ValueError, match='tag object'):
        scope.plan(root, tag, base)


def test_rename_out_of_runtime_does_not_hide_deleted_input(git_repo):
    root, git, base = git_repo
    (root / 'runtime.go').write_text('package fixture\n')
    git('add', '.')
    git('commit', '-qm', 'runtime')
    base = git('rev-parse', 'HEAD')
    git('mv', 'runtime.go', 'removed.md')
    git('commit', '-qm', 'rename')
    result = scope.plan(root, git('rev-parse', 'HEAD'), base)
    assert 'runtime.go' in result['changed_paths'] and result['integration']


@pytest.mark.parametrize('kind', ['docs', 'python'])
def test_narrow_checks_do_not_build_guest_or_consume_release_receipts(monkeypatch, kind):
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append((argv, kw)))
    monkeypatch.setenv('MARIAMEM_TEST_HOST', 'must-not-start')
    verify.check(kind)
    assert all(argv[0] != 'go' for argv, _ in calls)
    assert all('runtime_validation.py' not in ' '.join(argv) for argv, _ in calls)
    pytest_calls = [(a, kw) for a, kw in calls if 'pytest' in a]
    assert bool(pytest_calls) == (kind == 'python')
    for _, kw in pytest_calls:
        assert 'MARIAMEM_TEST_HOST' not in kw['env']


def test_workflow_has_no_external_runtime_receipt_dependency():
    text = (ROOT / '.github/workflows/check.yml').read_text()
    assert 'scripts/development_scope.py' in text
    assert 'runtime_validation.py' not in text and 'GITHUB_TOKEN' not in text
    assert 'actions: read' not in text
    assert 'fetch-depth: 0' in text
    assert "if: needs.scope.outputs.integration == 'true'" in text
    assert "check --scope '${{ needs.scope.outputs.check_scope }}'" in text
