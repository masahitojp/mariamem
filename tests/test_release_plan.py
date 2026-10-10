"""One dispatch, authenticated reuse, and publication gates without remote writes."""
import ast
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import release_plan as planner
from ci_release_reuse import GitHub, WORKFLOW
from generated_release import CONTRACT, PLATFORMS, expected_names

SHA = 'a' * 40


@pytest.fixture
def candidate(tmp_path):
    version = tmp_path / 'python/mariamem/_version.py'
    version.parent.mkdir(parents=True)
    version.write_text('GIT_TAG="v0.4.2"\nPYTHON_VERSION="0.4.2"\n')
    return tmp_path


def ready(commit=SHA):
    return {'version': 3, 'contract': CONTRACT, 'result': 'READY',
            'source_commit': commit, 'git_tag': 'v0.4.2', 'python_version': '0.4.2',
            'platforms': {platform: {} for platform in PLATFORMS},
            'assets': {name: 'c' * 64 for name in expected_names('0.4.2')}}


def bundle(record, reference=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as zipped:
        zipped.writestr('ci-ready.json', json.dumps(record))
        zipped.writestr('SHA256SUMS', ''.join(f'{sha}  {name}\n' for name, sha in record['assets'].items()))
        if reference:
            zipped.writestr('qualification.json', json.dumps(reference))
    return output.getvalue()


class FixtureGitHub(GitHub):
    """Exercise real GitHub digest/expiry/name checks with in-memory HTTP data."""
    def __init__(self, payload=None, name=None, expired=False, corrupt=False):
        self.payload = payload
        self.name = name or 'release-ready-' + SHA
        self.expired = expired
        self.corrupt = corrupt

    def json(self, path):
        if '/workflows/' in path:
            return {'workflow_runs': [{'id': 123, 'created_at': datetime.now(timezone.utc).isoformat()}]}
        if '/artifacts?' in path:
            return {'artifacts': [] if self.payload is None else [{
                'id': 1, 'name': self.name, 'expired': self.expired,
                'digest': 'sha256:' + ('0' * 64 if self.corrupt else hashlib.sha256(self.payload).hexdigest())}]}
        return {'path': WORKFLOW}

    def request(self, path):
        return io.BytesIO(self.payload)


def selected(candidate, api, validate=None):
    return planner.plan(candidate, SHA, 'release', api=api,
                        validate=validate or (lambda *args: None))


def job_condition(job):
    workflow = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    return re.search(rf'^  {job}:\n(?:.*\n)*?    if: (.+)$', workflow, re.M).group(1)


def runs_job(job, result, *, aggregate='success', publication='success',
             resolve='success', candidate_result='success', cancelled=False, ancestors_skipped=False):
    # Evaluate the actual, small boolean Actions expression. Model the implicit
    # success() guard too: the old workflow would fail the skipped-ancestor test.
    expression = job_condition(job)
    if ancestors_skipped and not re.search(r'\b(always|cancelled|success|failure)\(', expression):
        return False
    values = {'inputs.operation': result['operation'], 'needs.resolve.outputs.mode': result['mode'],
              'needs.resolve.result': resolve, 'needs.aggregate.result': aggregate,
              'needs.publication.result': publication, 'needs.candidate.result': candidate_result}
    for key, value in values.items():
        expression = expression.replace(key, repr(value))
    expression = expression.replace('always()', 'True').replace('cancelled()', str(cancelled))
    expression = re.sub(r'!(?!=)', ' not ', expression.replace('&&', ' and ').replace('||', ' or '))
    tree = ast.parse(expression.strip(), mode='eval')
    allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
               ast.Compare, ast.Eq, ast.NotEq, ast.Constant)
    assert all(isinstance(node, allowed) for node in ast.walk(tree))
    return eval(compile(tree, '<workflow-condition>', 'eval'), {'__builtins__': {}})


def test_release_without_ready_qualifies_once_then_publishes(candidate):
    result = selected(candidate, FixtureGitHub())
    assert result['mode'] == 'full'
    assert runs_job('guest', result) and runs_job('candidate', result)
    assert runs_job('verification', result)
    assert runs_job('publication', result) and runs_job('public_smoke', result)


def test_exact_ready_reuses_without_build_or_acceptance_then_publishes(candidate):
    checks = []
    result = selected(candidate, FixtureGitHub(bundle(ready())), lambda *args: checks.append(args))
    assert result['mode'] == 'guard-only'
    assert result['candidate_run'] == result['evidence_run'] == result['reused_ready_run'] == 123
    assert checks == [(candidate, SHA, 123, 123, ready())]
    assert not runs_job('guest', result) and not runs_job('candidate', result)
    assert runs_job('verification', result, ancestors_skipped=True, candidate_result='skipped')
    workflow = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    assert "if: needs.resolve.outputs.mode != 'guard-only'" in workflow
    assert runs_job('publication', result, ancestors_skipped=True)
    assert runs_job('public_smoke', result, ancestors_skipped=True)


@pytest.mark.parametrize('change', [
    {'source_commit': 'b' * 40}, {'git_tag': 'v0.4.1'}, {'python_version': '0.4.1'},
    {'result': 'NOT READY'}, {'platforms': {PLATFORMS[0]: {}}}, {'contract': 'legacy'},
    {'assets': {}},
])
def test_wrong_identity_or_not_ready_never_reuses(candidate, change):
    record = {**ready(), **change}
    def forbidden(*args):
        pytest.fail('invalid READY must not reach artifact restoration')
    result = selected(candidate, FixtureGitHub(bundle(record)), forbidden)
    assert result['mode'] == 'full'


def test_artifact_for_different_sha_not_selected(candidate):
    result = selected(candidate, FixtureGitHub(bundle(ready('b' * 40)), 'release-ready-' + 'b' * 40))
    assert result['mode'] == 'full'


@pytest.mark.parametrize('kind', ['missing', 'expired', 'corrupt-zip', 'missing-platform',
                                 'expired-evidence', 'source-hash', 'notice', 'harness'])
def test_unusable_artifacts_evidence_fall_back_in_same_plan(candidate, kind):
    api = FixtureGitHub(None if kind == 'missing' else bundle(ready()),
                        expired=kind == 'expired', corrupt=kind == 'corrupt-zip')
    def validate(*args):
        raise ValueError(kind)
    result = selected(candidate, api, validate)
    assert result['mode'] == 'full' and result['candidate_run'] == ''


def test_reused_receipt_follows_immutable_original_inputs(candidate):
    reference = {'version': 1, 'source_commit': SHA, 'candidate_run': 10, 'evidence_run': 20}
    checks = []
    result = selected(candidate, FixtureGitHub(bundle(ready(), reference)), lambda *args: checks.append(args))
    assert (result['candidate_run'], result['evidence_run'], result['reused_ready_run']) == (10, 20, 123)
    assert checks[0][2:4] == (10, 20)


def test_validate_reuse_rechecks_guard_in_disposable_source(candidate, monkeypatch):
    (candidate / 'scripts').mkdir()
    (candidate / 'scripts/release_generated_ci.py').write_text('# fixture')
    projects = []
    def run(args, check):
        assert check
        project = Path(args[args.index('--root') + 1])
        assert project != candidate and args[1] == str(candidate / 'scripts/release_generated_ci.py')
        projects.append(project)
        if args[2] == 'guard':
            target = project / 'build/release/ci-ready.json'
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(ready()))
    monkeypatch.setattr(planner.subprocess, 'run', run)
    planner.validate_reuse(candidate, SHA, 10, 20, ready())
    assert len(projects) == 2 and not projects[0].exists()
    assert not (candidate / 'build').exists()
    with pytest.raises(ValueError, match='identity differs'):
        planner.validate_reuse(candidate, SHA, 10, 20, {**ready(), 'assets': {'source.tar.gz': 'd' * 64}})
    assert not projects[-1].exists()


def test_failed_partial_restore_discards_scratch_before_full_fallback(candidate, monkeypatch):
    (candidate / 'scripts').mkdir()
    (candidate / 'scripts/release_generated_ci.py').write_text('# fixture')
    projects = []
    def fail(args, check):
        project = Path(args[args.index('--root') + 1])
        projects.append(project)
        (project / 'partial').write_text('untrusted partial restore')
        raise planner.subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(planner.subprocess, 'run', fail)
    result = selected(candidate, FixtureGitHub(bundle(ready())), planner.validate_reuse)
    assert result['mode'] == 'full'
    assert projects and not projects[0].exists()
    assert not (candidate / 'partial').exists() and not (candidate / 'build').exists()


@pytest.mark.parametrize('mode', ['full', 'guard-only'])
def test_not_ready_or_cancelled_never_publishes(mode):
    result = {'operation': 'release', 'mode': mode}
    assert not runs_job('publication', result, aggregate='failure', ancestors_skipped=mode != 'full')
    assert not runs_job('publication', result, resolve='failure')
    assert not runs_job('publication', result, cancelled=True)
    assert not runs_job('public_smoke', result, publication='skipped')


@pytest.mark.parametrize('reuse', [False, True])
def test_verify_can_be_ready_but_never_publish(candidate, reuse):
    result = planner.plan(candidate, SHA, 'verify', api=FixtureGitHub(bundle(ready()) if reuse else None),
                          validate=lambda *args: None)
    assert result['mode'] == ('guard-only' if reuse else 'full')
    assert runs_job('verification', result, ancestors_skipped=reuse)
    assert not runs_job('publication', result) and not runs_job('public_smoke', result)


def test_auto_does_not_accept_manual_run_ids(candidate):
    with pytest.raises(ValueError, match='auto selects'):
        planner.plan(candidate, SHA, 'release', candidate_run=123)


def test_workflow_normal_defaults_names_and_guard_remain():
    workflow = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    assert 'options: [verify, release, public-smoke-recovery]' in workflow
    assert 'default: verify' in workflow and 'default: auto' in workflow
    assert "run-name: '${{ inputs.operation }} -- ${{ inputs.label || inputs.candidate_ref }}'" in workflow
    assert 'python scripts/release_plan.py' in workflow
    assert 'candidate-source/scripts/release_generated_ci.py guard' in workflow
    assert 'candidate-source/scripts/ci_release_publish.py' in workflow
    assert 'release_generated_ci.py public-smoke' in workflow
    assert 'candidate-source/build/release/qualification.json' in workflow
    assert '[[ "$CANDIDATE_REF" =~ ^[0-9a-f]{40}$ ]] || exit 1' in workflow
    assert 'test "$sha" = "$CANDIDATE_REF"' in workflow


def test_explicit_runtime_intent_failure_never_falls_back(candidate, monkeypatch):
    monkeypatch.setattr(planner, 'read_intent', lambda root: {'explicit': True})
    def fail(*args):
        raise ValueError('invalid runtime evidence')
    monkeypatch.setattr(planner, 'validate_runtime', fail)
    api = FixtureGitHub()
    monkeypatch.setattr(api, 'json', lambda path: pytest.fail('must stop before READY discovery'))
    with pytest.raises(ValueError, match='invalid runtime evidence'):
        selected(candidate, api)


@pytest.mark.parametrize('ready_reuse', [False, True])
def test_runtime_proof_is_distinct_from_exact_ready(candidate, monkeypatch, ready_reuse):
    monkeypatch.setattr(planner, 'read_intent', lambda root: {'explicit': True})
    monkeypatch.setattr(planner, 'validate_runtime', lambda *args: {'result': 'PASS'})
    result = selected(candidate, FixtureGitHub(bundle(ready()) if ready_reuse else None))
    assert result['runtime_reused'] == 'true'
    assert result['mode'] == ('guard-only' if ready_reuse else 'full')
