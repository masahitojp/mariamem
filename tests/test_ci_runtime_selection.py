"""Cost boundaries must preserve selected runtime failures and their owners."""
from pathlib import Path
import re
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from development_scope import runtime_required, select


@pytest.mark.parametrize('paths', [
    ['AGENTS.md', 'docs/development.md', 'docs/project-status.md'],
    ['scripts/check_public.py', 'README.md'],
    ['scripts/release_prepare.py', 'tests/test_release_prepare.py'],
])
def test_inert_changes_skip_live_and_dump_but_keep_source_checks(paths):
    result = select(paths)
    assert result['check_scope'] in ('docs', 'python')
    assert not runtime_required(paths, result['reason'])
    for dependency in ['live.go', 'scripts/git_identity.py', 'scripts/build_alpha.py',
                       'scripts/development_scope.py', 'scripts/live_ci.py',
                       '.github/workflows/check.yml', 'unknown.py']:
        mixed = select(paths + [dependency])
        assert runtime_required(mixed['changed_paths'], mixed['reason'])


@pytest.mark.parametrize('paths,reason', [([], 'local changed-input classification'),
    (['README.md'], 'event diff unavailable'), (['scripts/check_public.py'], 'event base unavailable')])
def test_uncertain_diff_retains_runtime(paths, reason):
    assert runtime_required(paths, reason)


def job(text, name):
    return re.search(r'^  '+name+r':\n(.*?)(?=^  \S|\Z)', text, re.M | re.S)[1]


def test_ubuntu_worker_duplicates_have_required_integration_owner(monkeypatch):
    import verify
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, **kwargs: calls.append(argv))
    verify.integration()
    race = next(a for a in calls if a[:3] == ['go', 'test', '-race'])
    assert set(['./internal/generatedgo/code/base', './internal/generatedgo', './internal/guest', './internal/mysqlwire']) <= set(race)
    assert any('-run=TestWorkerTrapActualGuest' in a for a in calls)
    assert any('tests/test_python_wire.py' in a and 'tests/test_owned_snapshot.py' in a for a in calls)
    text = (ROOT/'.github/workflows/check.yml').read_text()
    from test_live_ci_workflow import validate_development_owners
    validate_development_owners(text)
    worker = job(text, 'worker-failure')
    for name in ['Host ownership races', 'Actual generated worker trap and independent DB survival',
                 'Wire regression and Snapshot/Fork after mapped temporary-table use']:
        assert f"- name: {name}\n        if: runner.os != 'Linux'" in worker
    assert 'tests/text_dedup_acceptance.py guest --suite ordinary' in worker
    assert 'tests/text_dedup_acceptance.py guest --source-commit' in worker


def test_django_prose_does_not_trigger_but_executable_examples_do():
    text = (ROOT/'.github/workflows/django-lifecycle.yml').read_text()
    from test_dump_ci_workflow import selected
    for event in ['push', 'pull_request']:
        block = re.search(r'^  '+event+r':\n(.*?)(?=^  \S|^\S)', text, re.M | re.S)[1]
        patterns = re.findall(r"^      - '([^']+)'$", block, re.M)
        assert not any(selected('docs/django-testing.md', p) for p in patterns)
        for path in ['docs/examples/django/manage.py', 'python/mariamem/django.py', 'guest/source.patch']:
            assert any(selected(path, p) for p in patterns)


def test_scope_cli_exports_runtime_decision(monkeypatch, tmp_path):
    import development_scope as scope
    output = tmp_path/'outputs'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    monkeypatch.setattr(scope, 'plan', lambda *a: select(['scripts/check_public.py']))
    monkeypatch.setattr(sys, 'argv', ['development_scope.py', '--candidate-sha', 'a'*40, '--base-sha', 'b'*40, '--github-output'])
    scope.main()
    assert 'run_runtime=false' in output.read_text().splitlines()


def test_daily_integration_reuses_host_for_source_live_smoke(monkeypatch):
    import verify
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append((argv, kw)))
    verify.integration()
    build = next(a for a, _ in calls if a[:2] == ['go', 'build'])
    host = build[build.index('-o') + 1]
    smoke = next(a for a, _ in calls if 'tests/live_acceptance/smoke.py' in a)
    assert smoke[-2:] == ['--host', host]
    assert any(a == ['go', 'run', './tests/live_acceptance/go_consumer', '-source-smoke'] for a, _ in calls)
    assert any('./internal/live' in a and '-race' in a for a, _ in calls)
    assert all('playwright' not in ' '.join(map(str, a)) and 'build_alpha.py' not in ' '.join(map(str, a)) for a, _ in calls)
