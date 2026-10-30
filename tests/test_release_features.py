"""Only authenticated exact-READY all-feature evidence may replace execution."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import release_features as features
import release_plan as planner
from generated_release import write
from test_release_plan import SHA, FixtureGitHub, bundle, candidate, ready, runs_job


def proof(run=123):
    return {'contract': features.CONTRACT_VERSION, 'source_commit': SHA, 'feature_run': run,
            'assets': ready()['assets'],
            'results': {job: 'success' for job in ('units', *features.FEATURES)}}


def reference(run=123):
    return {'version': 2, 'source_commit': SHA, 'candidate_run': 10,
            'evidence_run': 20, 'feature_run': run}


def feature_zip(record=None, name='features.json', duplicate=False):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as zipped:
        zipped.writestr(name, json.dumps(proof() if record is None else record))
        if duplicate:
            zipped.writestr('other.json', '{}')
    return output.getvalue()


class EvidenceGitHub(FixtureGitHub):
    """Use the real artifact transport, including original run, ZIP hash and expiry."""
    def __init__(self, feature=None, *, expired=False, corrupt=False):
        self.payloads = {1: bundle(ready(), reference()), 2: feature or feature_zip()}
        self.expired_feature = expired
        self.corrupt_feature = corrupt
        self.fetched = []

    def json(self, path):
        if '/artifacts?' in path:
            run = int(path.split('/runs/')[1].split('/')[0])
            number = 1 if run == 456 else 2
            name = ('release-ready-' if number == 1 else 'release-features-') + SHA
            payload = self.payloads[number]
            return {'artifacts': [{'id': number, 'name': name,
                    'expired': number == 2 and self.expired_feature,
                    'digest': 'sha256:' + ('0'*64 if number == 2 and self.corrupt_feature
                                          else hashlib.sha256(payload).hexdigest())}]}
        return super().json(path)

    def request(self, path):
        number = int(path.split('/artifacts/')[1].split('/')[0])
        self.fetched.append(number)
        return io.BytesIO(self.payloads[number])


def needs(reused=False):
    return {'resolve': {'result': 'success', 'outputs': {
                'features_reused': str(reused).lower(), 'mode': 'guard-only' if reused else 'full',
                'feature_run': '123' if reused else ''}},
            'verification': {'result': 'success'},
            **{job: {'result': 'skipped' if reused else 'success'}
               for job in ('runtime', 'units', *features.FEATURES)}}


def test_auto_ready_with_all_features_skips_units_runtime_and_six_campaigns(candidate):
    api = EvidenceGitHub()
    selected = planner.plan(candidate, SHA, 'release', api=api, runs=[456], validate=lambda *args: None)
    assert selected['mode'] == 'guard-only' and selected['features_reused'] == 'true'
    assert selected['feature_run'] == 123 and selected['reused_ready_run'] == 456
    assert api.fetched == [1, 2]
    for job in ('runtime', 'units', *features.FEATURES):
        assert not runs_job(job, selected)
    assert runs_job('verification', selected, ancestors_skipped=True)
    assert runs_job('publication', selected, ancestors_skipped=True)
    assert runs_job('public_smoke', selected, ancestors_skipped=True)


@pytest.mark.parametrize('kind', ['expired', 'zip-hash', 'source', 'run', 'wheel', 'incomplete',
                                 'failed', 'contract', 'unsafe-name', 'extra-member'])
def test_missing_or_changed_feature_proof_reruns_features_but_keeps_valid_core_ready(candidate, kind):
    record = proof()
    if kind == 'source': record['source_commit'] = 'b'*40
    if kind == 'run': record['feature_run'] = 456
    if kind == 'wheel': record['assets'][next(iter(record['assets']))] = 'd'*64
    if kind == 'incomplete': del record['results']['feature-live']
    if kind == 'failed': record['results']['feature-live'] = 'failure'
    if kind == 'contract': record['contract'] = 'old'
    api = EvidenceGitHub(feature_zip(record, '../features.json' if kind == 'unsafe-name' else 'features.json',
                                    duplicate=kind == 'extra-member'),
                         expired=kind == 'expired', corrupt=kind == 'zip-hash')
    result = planner.plan(candidate, SHA, 'release', api=api, runs=[456], validate=lambda *args: None)
    assert result['mode'] == 'guard-only' and result['features_reused'] == 'false'
    assert result['feature_run'] == ''
    for job in ('runtime', 'units', *features.FEATURES):
        assert runs_job(job, result)


def test_old_ready_without_feature_receipt_reruns_features(candidate):
    result = planner.plan(candidate, SHA, 'release', api=FixtureGitHub(bundle(ready())),
                          runs=[123], validate=lambda *args: None)
    assert result['mode'] == 'guard-only' and result['features_reused'] == 'false'
    assert runs_job('feature-live', result)


@pytest.mark.parametrize('reused', [False, True])
def test_actual_gate_cli_rejects_failed_missing_cancelled_and_unexpected_jobs(reused):
    good = needs(reused)
    def run(value):
        return subprocess.run([sys.executable, ROOT/'scripts/release_features.py', 'gate'],
                              env=dict(os.environ, NEEDS_JSON=json.dumps(value)), capture_output=True).returncode
    assert run(good) == 0
    for job in ('runtime', 'units', 'verification', *features.FEATURES):
        wrong = ('failure', 'cancelled', None, 'success' if reused and job != 'verification' else 'skipped')
        for result in wrong:
            value = copy.deepcopy(good)
            if result is None: del value[job]
            else: value[job]['result'] = result
            assert run(value) != 0, (job, result)
    bad = copy.deepcopy(good)
    del bad['resolve']['outputs']['features_reused']
    assert run(bad) != 0
    if reused:
        for key, value in [('mode', 'full'), ('feature_run', '')]:
            bad = copy.deepcopy(good); bad['resolve']['outputs'][key] = value
            assert run(bad) != 0


def test_fresh_proof_is_bound_to_guarded_assets_and_original_success_run(tmp_path):
    write(tmp_path/'build/release/ci-ready.json', ready())
    result = features.record(tmp_path, SHA, 123, 10, 20, needs())
    assert result == reference()
    assert json.loads((tmp_path/'build/release/features.json').read_text()) == proof()
    reused = tmp_path/'reused'
    write(reused/'build/release/ci-ready.json', ready())
    assert features.record(reused, SHA, 789, 10, 20, needs(True), EvidenceGitHub()) == reference()
    # It does not publish a new proof with run 789 and thereby reset artifact expiry.
    assert not (reused/'build/release/features.json').exists()


def test_expired_proof_after_plan_fails_aggregate_instead_of_publishing(tmp_path):
    write(tmp_path/'build/release/ci-ready.json', ready())
    with pytest.raises(ValueError, match='expired'):
        features.record(tmp_path, SHA, 789, 10, 20, needs(True), EvidenceGitHub(expired=True))
    assert not (tmp_path/'build/release/qualification.json').exists()


def test_fresh_receipt_cannot_be_minted_from_partial_success(tmp_path):
    write(tmp_path/'build/release/ci-ready.json', ready())
    value = needs(); value['feature-live']['result'] = 'skipped'
    with pytest.raises(ValueError): features.record(tmp_path, SHA, 123, 10, 20, value)
    assert not (tmp_path/'build/release/features.json').exists()


def test_workflow_rechecks_original_proof_after_guard_and_retains_publication_boundary():
    text = (ROOT/'.github/workflows/release-candidate-ready.yml').read_text()
    aggregate = text.split('  aggregate:\n')[1].split('  publication:\n')[0]
    assert aggregate.index('release_features.py gate') < aggregate.index('release_generated_ci.py guard')
    assert aggregate.index('release_generated_ci.py guard') < aggregate.index('release_features.py record')
    assert "if: needs.resolve.outputs.features_reused != 'true'" in aggregate
    assert 'name: release-features-${{ needs.resolve.outputs.source_sha }}' in aggregate
    assert 'candidate-source/build/release/qualification.json' in aggregate


def test_common_units_have_one_feature_owner_and_preserve_python_boundaries():
    text = (ROOT/'.github/workflows/release-candidate-ready.yml').read_text()
    units = text.split('  units:\n')[1].split('  runtime:\n')[0]
    assert "python: '3.11'" in units and "pytest: '7.0.0'" in units
    assert "python: '3.14'" in units and "pytest: '9.0.2'" in units
    assert 'runs-on: ubuntu-24.04' in units
    moved = ('test_routing.py', 'test_routing_pytest.py', 'test_routing_receipts.py',
             'test_preparation_migration_acceptance.py', 'test_dump_ci_workflow.py',
             'test_git_identity.py', 'test_dump_product_binding.py', 'test_dump_import_acceptance.py')
    called = '\n'.join((ROOT/'.github/workflows'/name).read_text() for name in
                       ('connection-routing.yml', 'preparation-migration.yml', 'dump-import-productization.yml'))
    for name in moved:
        assert units.count('tests/'+name) == 1 and 'tests/'+name not in called
    # Actual installed dump behavior and both-platform runtime campaigns stay in place.
    assert 'tests/test_dump_import.py' in called
    assert called.count('os: [') == 3


@pytest.mark.parametrize('mutation', ['empty-assets', 'bad-hash', 'source', 'platform', 'not-ready'])
def test_feature_proof_cannot_bind_an_incomplete_ready(mutation):
    value = ready()
    if mutation == 'empty-assets': value['assets'] = {}
    if mutation == 'bad-hash': value['assets'][next(iter(value['assets']))] = 'not-a-hash'
    if mutation == 'source': value['source_commit'] = 'b'*40
    if mutation == 'platform': value['platforms'] = {}
    if mutation == 'not-ready': value['result'] = 'NOT READY'
    p = proof(); p['assets'] = value['assets']
    with pytest.raises(ValueError): features.validate(p, SHA, 123, value)


def test_missing_feature_artifact_keeps_core_reuse(candidate):
    api = EvidenceGitHub()
    original = api.json
    def missing(path):
        if '/runs/123/artifacts?' in path: return {'artifacts': []}
        return original(path)
    api.json = missing
    result = planner.plan(candidate, SHA, 'verify', api=api, runs=[456], validate=lambda *args: None)
    assert result['mode'] == 'guard-only' and result['features_reused'] == 'false'
    assert not runs_job('publication', result)


@pytest.mark.parametrize('mode', ['full', 'acceptance-only', 'guard-only'])
def test_explicit_recovery_does_not_silently_skip_feature_execution(candidate, mode):
    result = planner.plan(candidate, SHA, 'verify', mode=mode,
                          candidate_run=None if mode == 'full' else 10,
                          evidence_run=20 if mode == 'guard-only' else None)
    assert result['features_reused'] == 'false' and result['feature_run'] == ''
    assert runs_job('feature-live', result)


@pytest.mark.parametrize('run', [None, '', True, -1])
def test_invalid_feature_reference_reruns_only_features(candidate, run):
    ref = reference(); ref['feature_run'] = run
    result = planner.plan(candidate, SHA, 'verify', api=FixtureGitHub(bundle(ready(), ref)),
                          runs=[123], validate=lambda *args: None)
    assert result['mode'] == 'guard-only' and result['features_reused'] == 'false'
