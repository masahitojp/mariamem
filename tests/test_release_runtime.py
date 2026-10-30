"""Sharing artifacts must retain the real wheel verifier and reject substitutions."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys

import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import release_runtime as runtime
from generated_release import read, write
from test_generated_release import host_wheel
from test_release_plan import job_text, runs_job


@pytest.fixture
def shared(host_wheel, monkeypatch):
    root, wheel, manifest, make = host_wheel
    root = root.resolve()
    record = root/'tests/evidence/alpha-wheel.json'
    data = read(record)
    data['host_buildinfo'] = 'original-host: go1.26.10\n'+data['host_buildinfo']
    write(record, data)
    monkeypatch.setattr(runtime, 'require_commit', lambda *args: None)
    monkeypatch.setattr(runtime, 'current_target', lambda root: {'platform': 'darwin-arm64'})
    monkeypatch.setattr(runtime, 'verify_go_binary', lambda *args: data['host_buildinfo'])
    return root, wheel, record


def test_stage_uses_exact_wheel_bytes_and_is_idempotent(shared):
    root, wheel, _ = shared
    selected, host = runtime.stage(root, 'a'*40)
    assert selected == wheel and host.read_bytes() == b'host'
    assert host.stat().st_mode & 0o111 == 0o111
    assert runtime.stage(root, 'a'*40) == (selected, host)


@pytest.mark.parametrize('failure', ['source', 'wheel-bytes', 'host-bytes', 'extra-wheel', 'path', 'platform', 'binary-source', 'buildinfo', 'symlink'])
def test_shared_runtime_rejects_wrong_or_ambiguous_inputs(shared, monkeypatch, failure):
    root, wheel, record = shared
    if failure == 'wheel-bytes': wheel.write_bytes(wheel.read_bytes()+b'corruption')
    elif failure == 'host-bytes': (root/'build/mariamem-host').write_bytes(b'other-host')
    elif failure == 'extra-wheel': (wheel.parent/'other.whl').write_bytes(b'extra')
    elif failure == 'path':
        data = read(record); data['wheel'] = '../'+wheel.name; write(record, data)
    elif failure == 'platform':
        monkeypatch.setattr(runtime, 'current_target', lambda root: {'platform': 'ubuntu24.04-x86_64'})
    elif failure == 'binary-source':
        def reject(*args): raise ValueError('binary source differs')
        monkeypatch.setattr(runtime, 'verify_go_binary', reject)
    elif failure == 'buildinfo': monkeypatch.setattr(runtime, 'verify_go_binary', lambda *args: 'host\nother flags')
    elif failure == 'symlink': (root/'build/mariamem-host').symlink_to(wheel)
    with pytest.raises(ValueError):
        runtime.stage(root, ('b' if failure == 'source' else 'a')*40)


def test_release_builds_one_wheel_and_every_feature_uses_it():
    text = (ROOT/'.github/workflows/release-candidate-ready.yml').read_text()
    assert text.count('python scripts/build_alpha.py --ci-candidate') == 1
    assert 'needs: [resolve, guest, core_darwin]' in text
    assert 'needs: [resolve, guest, core_ubuntu]' in text
    assert "if: needs.resolve.outputs.mode != 'full'" in text
    assert '--mode acceptance-only --candidate-run' in text
    candidate = job_text('candidate_darwin')
    core = job_text('core_darwin')
    assert 'build_alpha.py' not in candidate
    assert 'release-runtime-${{ env.RELEASE_RUNNER }}-${{ needs.resolve.outputs.source_sha }}' in candidate
    assert 'verify.py check\n' in core and 'verify.py integration --host build/mariamem-host' in core
    for name in ['live-host', 'dump-import-productization', 'django-lifecycle', 'connection-routing', 'preparation-migration', 'worker-failure']:
        called = (ROOT/'.github/workflows'/f'{name}.yml').read_text()
        assert 'release-runtime-${{ matrix.os }}-${{ inputs.source_commit }}' in called
        assert 'python scripts/release_runtime.py --source-commit "$SOURCE_COMMIT"' in called
        assert 'scripts/build_alpha.py --ci-candidate' not in called
        assert 'go build -p 1 -trimpath -o build/mariamem-host ' not in called
    installed = (ROOT/'tests/live_acceptance/installed.py').read_text()
    assert 'build_alpha.py' not in installed and 'stage(ROOT, args.expected_source_commit)' in installed


def test_candidate_cache_retains_race_compilation_but_never_skips_tests():
    text = (ROOT/'.github/workflows/release-candidate-ready.yml').read_text()
    candidate = job_text('core_darwin')
    restore = candidate.index('uses: actions/cache/restore@')
    discard = candidate.index('run: go clean -testcache')
    checks = candidate.index('python scripts/verify.py check')
    integration = candidate.index('python scripts/verify.py integration --host')
    save = candidate.index('uses: actions/cache/save@')
    assert restore < discard < checks < integration < save
    key = next(line for line in candidate.splitlines() if 'key: release-core-race-' in line)
    for boundary in ('runner.os', 'runner.arch', 'go1.26.10', "hashFiles('go.mod', 'go.sum')", 'needs.resolve.outputs.source_sha'):
        assert boundary in key
    assert 'restore-keys:' in candidate  # Later source revisions may reuse compilation.
    assert candidate.count('${{ steps.compiler-paths.outputs.build }}') == 2
    assert candidate.count('${{ steps.compiler-paths.outputs.modules }}') == 2
    assert 'key: ${{ steps.compiler-cache.outputs.cache-primary-key }}' in candidate
    assert "if: success() && needs.resolve.outputs.runtime_reused != 'true' && steps.compiler-cache.outputs.cache-hit != 'true'" in candidate
    # Cache outages/misses are optimization failures, never qualification bypasses.
    assert candidate.count('continue-on-error: true') == 2
    qualify = candidate.split('      - name: Qualify core and race', 1)[1].split('      - name: Save compiler', 1)[0]
    assert 'cache-hit' not in qualify and 'continue-on-error' not in qualify
    assert "if [ '${{ needs.resolve.outputs.runtime_reused }}' = true ]; then" in qualify
    assert 'go1.26.10 python scripts/verify.py integration' in qualify
    assert '-count=1' in (ROOT/'scripts/verify.py').read_text().split('def integration(', 1)[1]


def dependencies(job):
    value = re.search(r'^    needs: (.+)$', job_text(job), re.M)[1]
    return {name.strip() for name in value.strip('[]').split(',')}


@pytest.mark.parametrize('suffix,runner,platform', [('darwin', 'macos-15', 'darwin-arm64'),
                                                  ('ubuntu', 'ubuntu-24.04', 'ubuntu24.04-x86_64')])
def test_platform_pipeline_starts_core_without_guest_and_advances_independently(suffix, runner, platform):
    assert dependencies('guest') == {'resolve'}
    assert dependencies('core_'+suffix) == {'resolve', 'runtime'}
    assert dependencies('candidate_'+suffix) == {'resolve', 'guest', 'core_'+suffix}
    assert dependencies('verification_'+suffix) == {'resolve', 'candidate_'+suffix}
    core = job_text('core_'+suffix, expand_steps=True)
    freeze = job_text('candidate_'+suffix, expand_steps=True)
    verification = job_text('verification_'+suffix, expand_steps=True)
    for section in (core, freeze, verification):
        assert 'runs-on: '+runner in section
        assert 'RELEASE_PLATFORM: '+platform in section and 'RELEASE_RUNNER: '+runner in section
        assert 'ref: ${{ needs.resolve.outputs.source_sha }}' in section
    # Core uses the already tracked runtime and exact shared wheel. Canonical
    # guest/source closure still has to succeed before a handoff can be frozen.
    assert 'release-generated-inputs-' not in core and 'release_generated_ci.py freeze' not in core
    assert 'verify.py check' in core and 'verify.py integration --host build/mariamem-host' in core
    assert 'release-generated-inputs-${{ needs.resolve.outputs.source_sha }}' in freeze
    assert 'scripts/release_runtime.py --source-commit' in core and 'scripts/release_runtime.py --source-commit' in freeze
    assert 'scripts/verify_generated_runtime.py' in freeze and 'scripts/release_generated_ci.py freeze' in freeze
    assert 'verify.py check' not in freeze and 'verify.py integration' not in freeze
    assert 'cache: false' in verification and 'actions/cache/' not in verification
    assert 'release-candidate-${{ env.RELEASE_PLATFORM }}-${{ needs.resolve.outputs.source_sha }}' in verification
    assert 'generated_release_acceptance.py' in verification
    result = {'mode': 'full', 'operation': 'verify'}
    assert runs_job('verification_'+suffix, result, candidate_result='success')
    for failure in ('failure', 'cancelled', 'skipped'):
        assert not runs_job('verification_'+suffix, result, candidate_result=failure)


def test_both_platforms_share_the_same_step_definitions_and_frozen_proof():
    for phase in ('core', 'candidate', 'verification'):
        darwin = job_text(phase+'_darwin').split('    steps: &'+phase+'_steps\n')[1]
        ubuntu = job_text(phase+'_ubuntu', expand_steps=True).split('    steps:\n')[1]
        assert darwin == ubuntu
    core = job_text('core_darwin')
    freeze = job_text('candidate_darwin')
    name = 'release-core-runtime-proof-${{ env.RELEASE_PLATFORM }}-${{ needs.resolve.outputs.source_sha }}'
    assert name in core and name in freeze
    assert 'path: build/release/runtime-validation.json' in core
    assert 'path: build/release/' in freeze
    for section in (core, freeze):
        proof_step = section.split(name)[0].rsplit('      - name:', 1)[-1]
        assert "if: needs.resolve.outputs.runtime_reused == 'true'" in proof_step
    assert 'runtime_validation.py --candidate-sha' in core
    assert '--output build/release/runtime-validation.json' in core
    # Existing freeze logic authenticates the proof again before including it.
    helper = (ROOT/'scripts/release_generated_ci.py').read_text()
    assert 'verify_frozen(root,read(root/' in helper and 'paths.append(PROOF)' in helper


def qualification_needs(mode):
    result = {'resolve': {'result': 'success', 'outputs': {'mode': mode}}}
    result.update({job: {'result': 'success' if mode == 'full' else 'skipped'}
                   for job in ('guest', 'core_darwin', 'core_ubuntu', 'candidate_darwin', 'candidate_ubuntu')})
    result.update({job: {'result': 'success'} for job in ('verification_darwin', 'verification_ubuntu')})
    return result


def run_qualification_gate(needs):
    # Execute the actual final join; no duplicate implementation of its rules.
    section = job_text('verification')
    program = '\n'.join(line[10:] for line in section.split("python3 - <<'PYGATE'\n", 1)[1].split('          PYGATE', 1)[0].splitlines())
    return subprocess.run([sys.executable, '-c', program],
                          env=dict(os.environ, NEEDS_JSON=json.dumps(needs)), capture_output=True, text=True)


@pytest.mark.parametrize('mode', ['full', 'acceptance-only', 'guard-only'])
def test_final_join_accepts_only_the_complete_selected_route(mode):
    needs = qualification_needs(mode)
    assert dependencies('verification') == set(needs)
    result = run_qualification_gate(needs)
    assert result.returncode == 0, result.stderr
    assert 'verification' in dependencies('aggregate')
    # Reuse paths must survive the skipped full-only ancestors.
    for suffix in ('darwin', 'ubuntu'):
        assert runs_job('verification_'+suffix, {'mode': mode, 'operation': 'verify'},
                        ancestors_skipped=mode != 'full', candidate_result='success' if mode == 'full' else 'skipped')


@pytest.mark.parametrize('mode', ['full', 'acceptance-only', 'guard-only'])
@pytest.mark.parametrize('job', ['resolve', 'guest', 'core_darwin', 'core_ubuntu', 'candidate_darwin',
                                 'candidate_ubuntu', 'verification_darwin', 'verification_ubuntu'])
def test_final_join_blocks_missing_failed_cancelled_or_wrongly_skipped_work(mode, job):
    needs = qualification_needs(mode)
    expected = needs[job]['result']
    for wrong in ('failure', 'cancelled', 'skipped' if expected == 'success' else 'success'):
        needs[job]['result'] = wrong
        assert run_qualification_gate(needs).returncode != 0
    del needs[job]
    assert run_qualification_gate(needs).returncode != 0


def test_final_join_rejects_unknown_modes_and_extra_dependencies():
    needs = qualification_needs('auto')
    assert run_qualification_gate(needs).returncode != 0
    needs = qualification_needs('full'); needs['unexpected'] = {'result': 'success'}
    assert run_qualification_gate(needs).returncode != 0
