"""The native preview requires all jobs and all source-bound wheel artifacts."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from workflow_model import events, load, needs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import release_candidate_preview as preview
from native_target import platform_fields, target_metadata

COMMIT = 'a' * 40
GUEST = 'b' * 64
HOST = 'c' * 64
PACKAGE = '0.7.0'
INVENTORY = {'go.mod': 'd' * 64}
RUN = 123
WORKFLOW = 'e' * 40
INPUTS = 'f' * 64
RECEIPT = f'release-candidate-preview-{COMMIT}-attempt-2'


def qualification_jobs():
    jobs = {name: {'result': 'success'} for name in preview.REQUIRED_JOBS}
    jobs['resolve']['outputs'] = {'mode': 'full', 'runtime_reused': 'false',
                                  'features_reused': 'false', 'source_sha': COMMIT}
    return jobs


@pytest.mark.parametrize('job', sorted(preview.REQUIRED_JOBS))
def test_no_job_can_be_skipped(job):
    expected = qualification_jobs()
    preview.check_jobs(expected, COMMIT)
    expected[job]['result'] = 'skipped'
    with pytest.raises(ValueError, match=job):
        preview.check_jobs(expected, COMMIT)


@pytest.mark.parametrize('override', [{'mode': 'guard-only'}, {'runtime_reused': 'true'},
                                     {'features_reused': 'true'}, {'source_sha': 'e' * 40}])
def test_previous_ready_and_runtime_reuse_cannot_substitute(override):
    jobs = qualification_jobs()
    jobs['resolve']['outputs'].update(override)
    with pytest.raises(ValueError, match='qualification plan differs'):
        preview.check_jobs(jobs, COMMIT)


class Artifacts:
    def __init__(self):
        self.entries = {}
        self.ids = {}
        for target in preview.TARGETS:
            self.add(target)

    def artifact(self, run, name, commit, destination):
        assert (run, commit) == (RUN, COMMIT)
        preview.require(name in self.entries, 'missing artifact: ' + name)
        with zipfile.ZipFile(destination, 'w') as archive:
            for path, value in self.entries[name].items():
                archive.writestr(path, value if isinstance(value, bytes) else json.dumps(value))
        return {'run_id': run, 'artifact_id': self.ids.setdefault(name, len(self.ids) + 1),
                'name': name, 'zip_sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}

    def add(self, target):
        meta = target_metadata(target)
        name = preview.wheel_name(PACKAGE, target)
        wheel = target.encode()
        sha = hashlib.sha256(wheel).hexdigest()
        host = meta.get('host_name', 'mariamem-host')
        build = {'source_commit': COMMIT, 'source_files_sha256': INVENTORY, 'archive_checks_passed': True,
                 'host_buildinfo': (f'host: go1.26.11\n\tbuild\tvcs.revision={COMMIT}\n'
                                    f'\tbuild\tvcs.modified=false\n\tbuild\tCGO_ENABLED=0\n'
                                    f'\tbuild\tGOOS={meta["goos"]}\n\tbuild\tGOARCH={meta["goarch"]}\n'),
                 'wheel': 'build/dist/' + name, 'sha256': sha,
                 'manifest': {**platform_fields(meta), 'package_version': PACKAGE, 'guest_sha256': GUEST,
                              'runtime_kind': 'generated-go', 'public_release_ready': False, 'sha256': {host: HOST}}}
        report = {'contract': 'native-candidate-v1', 'status': 'PASS', 'target': target, 'source_commit': COMMIT,
                  'version': PACKAGE, 'guest_sha256': GUEST, 'wheel': name, 'wheel_sha256': sha, 'host_sha256': HOST,
                  'common_cases': {'tests': 3, 'failures': 0, 'errors': 0, 'skipped': 0},
                  'scenarios': dict.fromkeys(preview.SCENARIOS, 'PASS'), 'go_consumer': {'result': 'PASS'},
                  'sqlalchemy': {'result': 'PASS', 'wheel_sha256': sha}}
        if target == preview.UBUNTU:
            acceptance = b'{}'
            proof = {'version': 3, 'contract': preview.LEGACY_CONTRACT, 'result': 'READY', 'source_commit': COMMIT,
                     'platform': target, 'guest_sha256': GUEST, 'python_version': PACKAGE, 'assets': {name: sha},
                     'wheel_record': build, 'build_evidence_sha256': HOST, 'regeneration_sha256': HOST,
                     'acceptance_sha256': hashlib.sha256(acceptance).hexdigest()}
            self.entries['release-runtime-ubuntu-24.04-' + COMMIT] = {
                'build/dist/' + name: wheel, 'tests/evidence/alpha-wheel.json': build}
            self.entries['release-evidence-' + target + '-' + COMMIT] = {
                'build/release/ci-ready.json': proof, 'build/release/generated-acceptance.json': acceptance}
        elif target in (preview.LINUX_X86, preview.LINUX_ARM):
            self.entries['linux-wheel-' + target + '-' + COMMIT] = {
                'dist/' + name: wheel, 'linux-receipts/wheel.json': build,
                **{f'linux-receipts/{family}.json':
                   {'result': 'PASS', 'target': target, 'family': family, 'source_commit': COMMIT,
                    'wheel': name, 'sha256': sha, 'environment': {'machine': meta['architecture']},
                    'image_digests': ['image@sha256:' + HOST]} for family in preview.LIBCS}}
        elif target == preview.DARWIN:
            self.entries['macos-boundary-' + COMMIT] = {
                'build/dist/' + name: wheel, 'tests/evidence/alpha-wheel.json': build,
                'build/macos-boundary/acceptance.json': report}
        else:
            suffix = meta['goarch'] + '-' + COMMIT
            report['cases'] = {'tests': 18, 'failures': 0, 'errors': 0, 'skipped': 0}
            self.entries['windows-wheel-' + suffix] = {name: wheel}
            self.entries['windows-boundary-' + suffix] = {
                'tests/evidence/alpha-wheel.json': build, 'build/windows-boundary/acceptance.json': report}


def test_aggregate_binds_all_six_wheels_to_their_artifact_sources():
    result = preview.collect(Artifacts(), RUN, COMMIT, PACKAGE, GUEST, INVENTORY)
    assert set(result) == set(preview.TARGETS)
    for target, record in result.items():
        assert record['wheel_sha256'] == hashlib.sha256(target.encode()).hexdigest()
        assert all(ref['run_id'] == RUN for ref in record['artifact_refs'])


@pytest.mark.parametrize('failure', ['missing-arm64', 'missing-musl', 'wheel-bytes', 'source', 'scenario',
                                     'old-native', 'runtime-reuse', 'ubuntu-consumer', 'unsafe-path'])
def test_aggregate_rejects_incomplete_or_mixed_evidence(failure):
    api = Artifacts()
    windows = api.entries['windows-boundary-arm64-' + COMMIT]['build/windows-boundary/acceptance.json']
    linux = api.entries['linux-wheel-linux-x86_64-' + COMMIT]
    ubuntu = api.entries['release-evidence-' + preview.UBUNTU + '-' + COMMIT]
    if failure == 'missing-arm64':
        del api.entries['windows-wheel-arm64-' + COMMIT]
    elif failure == 'missing-musl':
        del linux['linux-receipts/musllinux_1_2.json']
    elif failure == 'wheel-bytes':
        linux['dist/' + preview.wheel_name(PACKAGE, preview.LINUX_X86)] = b'different'
    elif failure == 'source':
        windows['source_commit'] = 'e' * 40
    elif failure == 'scenario':
        del windows['scenarios']['parallel_fork_isolation']
    elif failure == 'old-native':
        del windows['contract']
    elif failure == 'runtime-reuse':
        ubuntu['build/release/ci-ready.json']['runtime_validation'] = {}
    elif failure == 'ubuntu-consumer':
        ubuntu['build/release/generated-acceptance.json'] = b'changed'
    else:
        linux['../extra'] = b'unexpected'
    with pytest.raises(ValueError):
        preview.collect(api, RUN, COMMIT, PACKAGE, GUEST, INVENTORY)


class CompletedQualification(Artifacts):
    def __init__(self):
        super().__init__()
        self.run = {'path': preview.WORKFLOW + '@ci/preview', 'id': RUN, 'head_sha': WORKFLOW,
                    'event': 'workflow_dispatch', 'status': 'completed',
                    'conclusion': 'success', 'run_attempt': 2}
        self.receipt = {'contract': preview.CONTRACT, 'result': 'READY', 'source_commit': COMMIT,
                        'workflow_commit': WORKFLOW, 'run_id': RUN, 'run_attempt': 2,
                        'guest_sha256': GUEST, 'inputs_sha256': INPUTS,
                        'targets': preview.collect(self, RUN, COMMIT, PACKAGE, GUEST, INVENTORY)}
        self.entries[RECEIPT] = {'preview-qualification.json': self.receipt}

    def json(self, path):
        assert path == f'/actions/runs/{RUN}'
        return self.run.copy()


@pytest.mark.parametrize('source_ok', [True, False])
def test_publication_stages_only_authenticated_assets(source_ok, tmp_path, monkeypatch):
    from published_assets import verify_downloads

    api = Artifacts()
    source = preview.source_name(PACKAGE)
    contents = b'canonical corresponding source'
    proof = api.entries['release-evidence-' + preview.UBUNTU + '-' + COMMIT]['build/release/ci-ready.json']
    proof['assets'][source] = hashlib.sha256(contents).hexdigest()
    api.entries['release-generated-inputs-' + COMMIT] = {
        'release/' + source: contents if source_ok else b'wrong source',
    }
    completed = CompletedQualification()
    api.json = completed.json
    receipt = dict(completed.receipt, targets=preview.collect(api, RUN, COMMIT, PACKAGE, GUEST, INVENTORY))
    api.entries[RECEIPT] = {'preview-qualification.json': receipt}
    monkeypatch.setattr(preview, 'preview_inputs', lambda root, commit: (PACKAGE, GUEST, INPUTS, INVENTORY))
    monkeypatch.setattr(preview, 'version', lambda root: {'GIT_TAG': 'v' + PACKAGE})
    destination = tmp_path / 'publish'
    if not source_ok:
        with pytest.raises(ValueError, match='corresponding source digest differs'):
            preview.stage_publication(api, RUN, COMMIT, WORKFLOW, tmp_path, destination)
        assert list(tmp_path.iterdir()) == []
        return
    reference = preview.stage_publication(api, RUN, COMMIT, WORKFLOW, tmp_path, destination)
    expected_assets = {preview.wheel_name(PACKAGE, target): hashlib.sha256(target.encode()).hexdigest()
                       for target in preview.TARGETS}
    expected_assets[source] = hashlib.sha256(contents).hexdigest()
    provenance = destination / f'mariamem-{PACKAGE}-provenance.json'
    payload = json.loads(provenance.read_text())
    assert payload['assets'] == expected_assets
    assert payload['qualification'] == reference
    sums = destination / 'SHA256SUMS'
    verify_downloads(destination, {**expected_assets, provenance.name: preview.digest(provenance),
                                   sums.name: preview.digest(sums)})
    from pypi_release import checksums, verify_origin
    hashes = checksums(sums.read_text())
    release = {'tag_name': 'v' + PACKAGE, 'draft': False, 'prerelease': False,
               'assets': [{'name': path.name} for path in destination.iterdir()]}
    pypi = verify_origin(None, payload, hashes, release, COMMIT, 'v' + PACKAGE, 'example/repository')
    assert pypi == {preview.wheel_name(PACKAGE, target): expected_assets[preview.wheel_name(PACKAGE, target)]
                    for target in preview.TARGETS if target != preview.UBUNTU}
    release['assets'].pop()
    with pytest.raises(ValueError, match='six-target GitHub release filenames differ'):
        verify_origin(None, payload, hashes, release, COMMIT, 'v' + PACKAGE, 'example/repository')


def test_reuse_authenticates_latest_six_target_receipt():
    api = CompletedQualification()
    ref = preview.revalidate(api, RUN, COMMIT, WORKFLOW, PACKAGE, GUEST, INPUTS, INVENTORY)
    assert ref['run_id'] == RUN
    assert ref['name'] == RECEIPT
    assert ref['artifact_id'] == api.ids[RECEIPT]


@pytest.mark.parametrize('change', [
    {'path': '.github/workflows/other.yml'}, {'head_sha': COMMIT},
    {'status': 'in_progress'}, {'conclusion': 'failure'},
    {'run_attempt': 3}, {'run_attempt': True},
])
def test_reuse_requires_latest_success_on_exact_workflow(change):
    api = CompletedQualification()
    api.run.update(change)
    with pytest.raises(ValueError):
        preview.revalidate(api, RUN, COMMIT, WORKFLOW, PACKAGE, GUEST, INPUTS, INVENTORY)


@pytest.mark.parametrize('change', [
    {'contract': preview.LEGACY_CONTRACT}, {'result': 'NOT READY'}, {'source_commit': WORKFLOW},
    {'run_attempt': 1}, {'guest_sha256': INPUTS}, {'inputs_sha256': GUEST},
    {'targets': {}}, {'targets': {'ubuntu24.04-x86_64': {}, 'darwin-arm64': {}}},
])
def test_reuse_rejects_mismatched_qualification(change):
    api = CompletedQualification()
    api.receipt.update(change)
    with pytest.raises(ValueError, match='READY'):
        preview.revalidate(api, RUN, COMMIT, WORKFLOW, PACKAGE, GUEST, INPUTS, INVENTORY)


def test_reuse_rejects_reuploaded_identical_bytes():
    api = CompletedQualification()
    api.ids['windows-wheel-arm64-' + COMMIT] += 100
    with pytest.raises(ValueError, match='wheel or artifact identity differs'):
        preview.revalidate(api, RUN, COMMIT, WORKFLOW, PACKAGE, GUEST, INPUTS, INVENTORY)


def test_reuse_rejects_run_restarted_during_validation(monkeypatch):
    api = CompletedQualification()
    first = api.run.copy()
    second = {**first, 'run_attempt': 3}
    metadata = iter((first, second))
    monkeypatch.setattr(api, 'json', lambda _: next(metadata))
    with pytest.raises(ValueError, match='restarted during validation'):
        preview.revalidate(api, RUN, COMMIT, WORKFLOW, PACKAGE, GUEST, INPUTS, INVENTORY)


class DiscoverableQualification(CompletedQualification):
    def json(self, path):
        if path.startswith('/actions/workflows/'):
            assert f'head_sha={WORKFLOW}' in path and 'status=success' in path
            return {'workflow_runs': [{'id': RUN + 1}, {'id': RUN - 1}, {'id': RUN}]}
        if path == f'/actions/runs/{RUN - 1}':
            return {**self.run, 'id': RUN - 1, 'conclusion': 'failure'}
        return super().json(path)


def test_auto_discovers_exact_qualification_after_rejected_run():
    api = DiscoverableQualification()
    reference = preview.select_reuse(api, RUN + 1, COMMIT, WORKFLOW, PACKAGE, GUEST, INPUTS, INVENTORY)
    assert reference['run_id'] == RUN
    assert reference['run_attempt'] == 2


@pytest.mark.parametrize('reason', ['missing', 'stale', 'unavailable'])
def test_auto_falls_back_to_full(reason, monkeypatch, tmp_path):
    api = DiscoverableQualification()
    if reason == 'missing':
        del api.entries[RECEIPT]
    elif reason == 'stale':
        api.run['run_attempt'] += 1
    else:
        def unavailable(path):
            raise OSError('GitHub API unavailable')
        monkeypatch.setattr(api, 'json', unavailable)
    reference = preview.select_reuse(api, RUN + 1, COMMIT, WORKFLOW, PACKAGE, GUEST, INPUTS, INVENTORY)
    assert reference is None
    output = tmp_path / 'output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    preview.write_selection(reference)
    assert output.read_text().splitlines() == ['mode=full', 'runtime_reused=false', 'features_reused=false']


@pytest.mark.parametrize('changed_attempt', [False, True])
def test_auto_reuse_records_original_full_receipt(changed_attempt, monkeypatch, tmp_path):
    api = DiscoverableQualification()
    reference = preview.select_reuse(api, RUN + 1, COMMIT, WORKFLOW, PACKAGE, GUEST, INPUTS, INVENTORY)
    output = tmp_path / 'output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    preview.write_selection(reference)
    selection = dict(line.split('=', 1) for line in output.read_text().splitlines())
    jobs = {name: {'result': 'skipped'} for name in preview.REQUIRED_JOBS}
    jobs['resolve'] = {'result': 'success', 'outputs': {**selection, 'source_sha': COMMIT}}
    assert selection['mode'] == 'preview-reuse'
    preview.check_jobs(jobs, COMMIT, reuse=True)
    with pytest.raises(ValueError, match='must be success'):
        preview.check_jobs(jobs, COMMIT)
    receipt = tmp_path / 'receipt.json'
    for key, value in {'GITHUB_RUN_ID': str(RUN + 1), 'GITHUB_RUN_ATTEMPT': '1',
                       'SOURCE_SHA': COMMIT, 'WORKFLOW_SHA': WORKFLOW, 'NEEDS_JSON': json.dumps(jobs),
                       'GITHUB_REPOSITORY': 'example/project', 'GITHUB_TOKEN': 'test'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(preview, 'GitHub', lambda *_: api)
    monkeypatch.setattr(sys, 'argv', ['preview', '--root', str(tmp_path), '--output', str(receipt)])
    if changed_attempt:
        api.run['run_attempt'] += 1
        with pytest.raises(ValueError, match='changed after selection'):
            preview.main()
        assert json.loads(receipt.read_text())['result'] == 'NOT READY'
    else:
        preview.main()
        result = json.loads(receipt.read_text())
        assert result['result'] == 'READY'
        assert result['reused_qualification'] == reference
        assert 'targets' not in result


def test_auto_reused_receipt_cannot_become_an_original_full_receipt():
    api = CompletedQualification()
    api.receipt['reused_qualification'] = api.receipt.pop('targets')
    with pytest.raises(ValueError, match='identity differs'):
        preview.revalidate(api, RUN, COMMIT, WORKFLOW, PACKAGE, GUEST, INPUTS, INVENTORY)


def test_preview_uses_one_legacy_ubuntu_lane_and_cannot_publish():
    model = load(ROOT / '.github/workflows/release-candidate-ready.yml')
    assert events(model)['workflow_dispatch']['inputs']['native_preview']['default'] is False
    jobs = model['jobs']
    assert needs(jobs['preview-aggregate']) == preview.REQUIRED_JOBS
    assert jobs['preview-aggregate']['if'].find('inputs.native_preview') >= 0
    for name in ('core_darwin', 'candidate_darwin', 'verification_darwin', 'verification',
                 'aggregate', 'publication', 'public_smoke_recovery', 'pypi_verify',
                 'pypi_publication', 'additional_plan', 'additional_publication'):
        assert '!inputs.native_preview' in jobs[name]['if'], name
    for name in preview.FEATURES:
        assert jobs[name]['with']['ubuntu_only'] == '${{ inputs.native_preview }}'
    upload = jobs['preview-aggregate']['steps'][-1]
    assert upload['with']['name'] == (
        'release-candidate-preview-${{ needs.resolve.outputs.source_sha }}-attempt-${{ github.run_attempt }}')
    assert 'overwrite' not in upload['with']
    assert upload['with']['path'] == 'preview-qualification.json'


def test_auto_reuse_skips_full_lanes_and_preserves_explicit_full_selection():
    jobs = load(ROOT / '.github/workflows/release-candidate-ready.yml')['jobs']
    resolve = jobs['resolve']
    assert resolve['outputs']['preview_reuse'] == '${{ steps.plan.outputs.preview_reuse }}'
    plan = next(step['run'] for step in resolve['steps'] if step.get('id') == 'plan')
    assert 'if [ "$MODE" = auto ]; then' in plan
    assert '--select-reuse' in plan
    assert 'mode=full runtime_reused=false features_reused=false' in plan
    for name in ('units', 'runtime', *preview.FEATURES):
        assert "needs.resolve.outputs.features_reused != 'true'" == jobs[name]['if']
    for name in ('guest', 'core_ubuntu', 'candidate_ubuntu', 'preview-windows', 'preview-macos', 'preview-linux'):
        assert "needs.resolve.outputs.mode == 'full'" in jobs[name]['if']
    assert "needs.resolve.outputs.mode != 'preview-reuse'" in jobs['verification_ubuntu']['if']


@pytest.mark.parametrize(('workflow', 'job_names', 'guard'), [
    ('release-candidate-ready', ('runtime', 'guest', 'candidate_ubuntu', 'verification_ubuntu'),
     'inputs.native_preview'),
    ('macos-native-candidate', ('native',), ''),
    ('windows-boundary', ('native',), 'inputs.source_commit'),
    ('linux-wheel', ('wheel',), 'inputs.source_commit'),
    ('live-host', ('native-reference', 'live'), 'inputs.ubuntu_only'),
    ('dump-import-productization', ('native-reference', 'guest-comparison'), 'inputs.ubuntu_only'),
    ('django-lifecycle', ('native', 'recipe'), 'inputs.ubuntu_only'),
    ('connection-routing', ('native',), 'inputs.ubuntu_only'),
    ('preparation-migration', ('native',), 'inputs.ubuntu_only'),
    ('worker-failure', ('worker-failure-native', 'worker-failure'), 'inputs.ubuntu_only'),
])
def test_failed_job_retry_replaces_only_the_rerun_jobs_uploads(workflow, job_names, guard):
    jobs = load(ROOT / f'.github/workflows/{workflow}.yml')['jobs']
    expected = '${{ ' + (guard + ' && ' if guard else '') + 'github.run_attempt > 1 }}'
    for name in job_names:
        uploads = [step['with'] for step in jobs[name]['steps']
                   if step.get('uses', '').startswith('actions/upload-artifact@')]
        assert uploads, name
        for upload in uploads:
            assert upload['overwrite'] == expected
            assert 'github.run_attempt' not in upload['name']


@pytest.mark.parametrize('bad', [
    {'OPERATION': 'release'}, {'OPERATION': 'public-smoke-recovery'}, {'ADDITIONAL': 'true'},
    {'MODE': 'guard-only'}, {'CANDIDATE_RUN': '42'}, {'EVIDENCE_RUN': '42'}, {'PUBLISHED_TAG': 'v0.7.0'},
    {'SMOKE_REF': COMMIT},
])
def test_invalid_preview_dispatch_is_rejected_before_git(bad, tmp_path):
    model = load(ROOT / '.github/workflows/release-candidate-ready.yml')
    source = next(step['run'] for step in model['jobs']['resolve']['steps'] if step.get('id') == 'source')
    shell = source.split('git fetch', 1)[0]
    env = dict(os.environ, CANDIDATE_REF=COMMIT, MODE='auto', CANDIDATE_RUN='', EVIDENCE_RUN='',
               NATIVE_PREVIEW='true', OPERATION='verify', ADDITIONAL='false', PUBLISHED_TAG='', SMOKE_REF='')
    subprocess.run(['bash', '-e', '-c', shell], cwd=tmp_path, env=env, check=True)
    result = subprocess.run(['bash', '-e', '-c', shell], cwd=tmp_path, env={**env, **bad})
    assert result.returncode != 0
