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
from live_ci import verify_gate
from live_selection import select as families


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


@pytest.mark.parametrize('doc', ['README.md', 'AGENTS.md', 'docs/development.md',
                                'docs/benchmarks/go126-vs-go127-evidence/statistics.csv'])
def test_documentation_does_not_expand_a_runtime_selection(doc):
    assert families(['mariamemtest/fixture.go', doc], 'pull_request', 'unknown/runtime input') == families(
        ['mariamemtest/fixture.go'], 'pull_request', 'unknown/runtime input')


def g1_needs():
    return {'scope': {'result': 'success', 'outputs': {
        'run_live': 'true', 'pull_request_draft': 'false', 'native_reference': 'false',
        'mac_integration': 'false', 'g1': 'true', 'live_runtime': 'false',
        'examples': 'false', 'installed': 'true'}},
        'native-reference': {'result': 'skipped'}, 'live': {'result': 'success'}}


def test_g1_accepts_only_the_intended_native_skip():
    verify_gate(g1_needs())
    for job in ['scope', 'native-reference', 'live']:
        for status in ['failure', 'cancelled']:
            needs = g1_needs(); needs[job]['result'] = status
            with pytest.raises(AssertionError): verify_gate(needs)
    for key in ['live_runtime', 'examples']:
        needs = g1_needs(); needs['scope']['outputs'][key] = 'true'
        with pytest.raises(AssertionError): verify_gate(needs)
    needs = g1_needs(); needs['live']['result'] = 'skipped'
    with pytest.raises(AssertionError): verify_gate(needs)


def job(text, name):
    return re.search(r'^  '+name+r':\n(.*?)(?=^  \S|\Z)', text, re.M | re.S)[1]


def test_browser_setup_and_live_job_follow_native_selection():
    text = (ROOT/'.github/workflows/live-host.yml').read_text()
    assert "if: needs.scope.outputs.run_live == 'true' && needs.scope.outputs.native_reference == 'true'" in job(text, 'native-reference')
    live = job(text, 'live')
    expression = re.search(r'if: >-\n\s*\$\{\{ (.*?) \}\}', live, re.S)[1]
    for selected in ['true', 'false']:
        for result in ['success', 'skipped', 'failure', 'cancelled']:
            expr = expression.replace("!cancelled()", 'True')
            for key, value in [('needs.scope.result', 'success'), ('needs.scope.outputs.run_live', 'true'),
                               ('needs.scope.outputs.native_reference', selected), ('needs.native-reference.result', result)]:
                expr = expr.replace(key, repr(value))
            actual = eval(' '.join(expr.replace('&&', 'and').replace('||', 'or').split()), {'__builtins__': {}}, {})
            assert actual == (result == ('success' if selected == 'true' else 'skipped'))
    assert live.count("if: needs.scope.outputs.native_reference == 'true'\n") == 3
    assert 'if [[ "${{ needs.scope.outputs.native_reference }}" == true ]]; then' in live


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


@pytest.mark.parametrize('native,canonical', [('false', 'false'), ('true', 'false'), ('false', 'true')])
def test_dependency_setup_skips_unused_browser_and_clients(tmp_path, native, canonical):
    text = (ROOT/'.github/workflows/live-host.yml').read_text()
    step = text.split('      - name: Pinned SDK/browser and existing regression inputs\n', 1)[1].split('      - uses:', 1)[0]
    script = step.split('        run: |\n', 1)[1]
    script = '\n'.join(line[10:] for line in script.splitlines())
    script = script.replace('${{ needs.scope.outputs.native_reference }}', native).replace('${{ needs.scope.outputs.mac_integration }}', canonical)
    fake = tmp_path/'python'
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$SETUP_LOG"\n')
    fake.chmod(0o755)
    log = tmp_path/'commands'
    subprocess.run(['bash', '-eu', '-c', script], check=True, env=dict(os.environ,
        PATH=str(tmp_path)+os.pathsep+os.environ['PATH'], PY311=str(fake), PY314=str(fake),
        RUNNER_OS='Linux', SETUP_LOG=str(log)))
    actual = log.read_text()
    assert ('-m playwright install' in actual) == (native == 'true')
    assert ('requirements.lock.txt' in actual) == (native == 'true' or canonical == 'true')
    assert 'build==1.6.1' in actual
    if native == canonical == 'false':
        assert actual.splitlines()[0] == 'scripts/git_identity.py inspect HEAD'
        assert len([line for line in actual.splitlines() if line.startswith('-m pip')]) == 1
        assert 'PyMySQL==1.2.3' in actual


@pytest.mark.parametrize('path,expected', [('mariamemtest/fixture.go', 'false'), ('live.go', 'true')])
def test_live_scope_exports_native_requirement(monkeypatch, tmp_path, path, expected):
    import live_ci
    event = tmp_path/'event'; event.write_text('{"pull_request":{"draft":false}}')
    output = tmp_path/'output'
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'pull_request')
    monkeypatch.setenv('GITHUB_EVENT_PATH', str(event))
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    monkeypatch.setattr(live_ci, 'plan', lambda *a: select([path]))
    monkeypatch.setattr(sys, 'argv', ['live_ci.py', 'scope', '--candidate-sha', 'a'*40, '--github-output'])
    live_ci.main()
    assert 'native_reference='+expected in output.read_text().splitlines()
