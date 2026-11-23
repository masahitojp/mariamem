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
    with pytest.raises(ValueError, match='fresh qualification'):
        preview.check_jobs(jobs, COMMIT)


class Artifacts:
    def __init__(self):
        self.entries = {}
        for target in preview.TARGETS:
            self.add(target)

    def artifact(self, run, name, commit, destination):
        assert (run, commit) == (RUN, COMMIT)
        preview.require(name in self.entries, 'missing artifact: ' + name)
        with zipfile.ZipFile(destination, 'w') as archive:
            for path, value in self.entries[name].items():
                archive.writestr(path, value if isinstance(value, bytes) else json.dumps(value))
        return {'run_id': run, 'name': name, 'zip_sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}

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
    assert upload['with']['name'] == 'release-candidate-preview-${{ needs.resolve.outputs.source_sha }}'
    assert upload['with']['path'] == 'preview-qualification.json'


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
