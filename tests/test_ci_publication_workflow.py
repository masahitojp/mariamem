"""Keep the CI publication boundary fail-closed without executing remote writes."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ci_release_summary import publication_rows
from test_release_plan import job_text
from workflow_model import load, needs, events, steps, commands, action


@pytest.mark.parametrize('job,mode,modern,fail', [
    ('aggregate', 'guard-only', True, False), ('aggregate', 'full', True, False),
    ('aggregate', 'full', False, False), ('aggregate', 'full', True, True),
    ('aggregate', 'full', False, True),
    ('verification', 'guard-only', True, False), ('verification', 'guard-only', True, True),
    ('verification', 'guard-only', False, False), ('verification', 'full', True, False),
    ('verification', 'acceptance-only', True, False),
])
def test_actual_restore_shell_keeps_one_guard_and_stops_on_failure(tmp_path, job, mode, modern, fail):
    model = load(ROOT/'.github/workflows/release-candidate-ready.yml')
    section = model['jobs']['verification_darwin' if job == 'verification' else job]
    found = [step for step in section['steps'] if (step.get('id') == 'restore' if job == 'verification' else step.get('name', '').startswith('Restore and guard both platforms once'))]
    assert len(found) == 1
    shell = found[0]['run']
    shell = shell.replace('${{ env.RELEASE_PLATFORM }}', 'darwin-arm64')
    assert '${{' not in shell
    binary = tmp_path/'bin'; binary.mkdir()
    fake = binary/'python'
    fake.write_text('#!'+sys.executable+'''\nimport json, os, pathlib, sys
command = sys.argv[2]
with open('commands.jsonl', 'a') as stream: stream.write(json.dumps(command)+'\\n')
if command == '--help':
    print('restore-guard' if os.environ['MODERN'] == '1' else 'restore guard')
elif os.environ['FAIL'] == '1':
    raise SystemExit(1)
elif command in ('restore-guard', 'guard'):
    target = pathlib.Path('candidate-source/build/release/ci-ready.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"result":"READY"}')
''')
    fake.chmod(0o755)
    (tmp_path/'candidate-input').mkdir()
    (tmp_path/'candidate-input/candidate-handoff.sha256').write_text('b'*64)
    output = tmp_path/'outputs'; output.touch()
    env = dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'],
               MODE=mode, SOURCE_SHA='a'*40, CANDIDATE_RUN='10', EVIDENCE_RUN='20',
               GITHUB_OUTPUT=str(output), GITHUB_STEP_SUMMARY=str(tmp_path/'summary'),
               RUNNER_TEMP=str(tmp_path), MODERN=str(int(modern)), FAIL=str(int(fail)))
    result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', shell], cwd=tmp_path,
                            env=env, capture_output=True, text=True)
    assert (result.returncode != 0) == fail, result.stderr
    calls = [json.loads(line) for line in (tmp_path/'commands.jsonl').read_text().splitlines()]
    combined = modern and (job == 'aggregate' or mode == 'guard-only')
    expected = ['--help', 'restore-guard' if combined else ('restore' if job == 'aggregate' else 'restore-platform')]
    if job == 'aggregate' and not modern and not fail: expected += ['guard']
    assert calls == expected
    if job == 'verification':
        assert output.read_text() == ('' if fail else 'guarded='+str(combined).lower()+'\n')
        assert any(step.get("if") == "always() && steps.restore.outcome == 'success' && steps.restore.outputs.guarded != 'true'" for step in section["steps"])
    if fail: assert not (tmp_path/'candidate-source/build/release/ci-ready.json').exists()


def test_publication_job_gate_and_handoff():
    model = load(ROOT / '.github/workflows/release-candidate-ready.yml')
    jobs = model['jobs']
    publication = jobs['publication']
    normal = '\n'.join(step.get('run', '') for step in publication['steps'])
    recovery = jobs['public_smoke_recovery']
    all_commands = commands(model)
    operation = events(model)['workflow_dispatch']['inputs']['operation']
    assert operation['default'] == 'verify'
    assert operation['options'] == ['verify', 'release', 'public-smoke-recovery']
    assert publication['if'] == "always() && !cancelled() && inputs.operation == 'release' && needs.resolve.result == 'success' && needs.aggregate.result == 'success'"
    assert publication['permissions']['contents'] == 'write'
    assert all(job.get('permissions', {}).get('contents') != 'write' for name, job in jobs.items() if name not in ('publication', 'public_smoke_recovery'))
    assert publication['concurrency']['cancel-in-progress'] is False
    assert 'environment' not in publication
    assert 'release_generated_ci.py restore' not in normal
    assert 'release_generated_ci.py guard' not in normal
    assert '--candidate-run "$CANDIDATE_RUN" --evidence-run "$EVIDENCE_RUN"' in normal
    assert 'candidate-source/scripts/ci_release_publish.py' in normal
    assert any(step.get('env', {}).get('EVIDENCE_RUN') == '${{ github.run_id }}' for step in publication['steps'])
    assert 'config user.name' in normal and 'args+=(--dry-run)' not in normal
    assert jobs['public_smoke']['if'] == "always() && !cancelled() && inputs.operation == 'release' && needs.resolve.result == 'success' && needs.publication.result == 'success'"
    for job in (publication, recovery):
        code = '\n'.join(step.get('run', '') for step in job['steps'])
        assert 'build_alpha.py' not in code and 'build_generated_guest.py' not in code
    assert 'build_generated_guest.py --repetitions 2' in all_commands
    assert 'regenerate_release_guest.py' in all_commands
    assert 'compile_guest_aot.py' not in all_commands and 'package_native.py' not in all_commands
    assert 'build_alpha.py --ci-candidate\n' in all_commands
    assert 'build_alpha.py --ci-candidate \\' not in all_commands
    assert 'generated_release_acceptance.py' in all_commands
    assert 'ubuntu-24.04-arm' in str(model)
    for platform, runner in [('darwin-arm64', 'macos-15'), ('ubuntu24.04-x86_64', 'ubuntu-24.04')]:
        assert any(job.get('runs-on') == runner and job.get('env', {}).get('RELEASE_PLATFORM') == platform for job in jobs.values())
        assert any(cell.get('platform') == platform for cell in jobs['public_smoke']['strategy']['matrix']['include'])
    names = [step.get('with', {}).get('name', '') for step in steps(model)]
    assert any('release-candidate-${{ env.RELEASE_PLATFORM }}-' in name for name in names)
    assert any('release-evidence-${{ env.RELEASE_PLATFORM }}-' in name for name in names)


def test_summary_exposes_publication_failure(tmp_path, monkeypatch):
    release = tmp_path / 'build/release'
    release.mkdir(parents=True)
    (release / 'ci-publication.json').write_text(json.dumps({
        'status': 'FAILED', 'stage': 'uploaded-hashes', 'error': 'hash mismatch',
        'git_tag': 'v0.1.0-alpha.3'}))
    monkeypatch.setenv('PUBLISH_RESULT', 'failure')
    summary = '\n'.join(publication_rows(tmp_path))
    assert 'Publication: **FAILED**' in summary
    assert 'hash mismatch' in summary and 'uploaded-hashes' in summary
    assert 'never moved, deleted, or replaced' in summary


FEATURES = {
    'feature-live': 'live-host', 'feature-dump': 'dump-import-productization',
    'feature-django': 'django-lifecycle', 'feature-routing': 'connection-routing',
    'feature-preparation': 'preparation-migration', 'feature-sql': 'worker-failure',
}


def test_heavy_suites_are_release_only_and_use_resolved_candidate():
    model = load(ROOT / '.github/workflows/release-candidate-ready.yml')
    aggregate = model['jobs']['aggregate']
    for job, filename in FEATURES.items():
        caller = model['jobs'][job]
        assert needs(caller) == {'resolve', 'runtime', 'units'}
        assert caller['uses'] == './.github/workflows/'+filename+'.yml'
        assert caller['with']['source_commit'] == '${{ needs.resolve.outputs.source_sha }}'
        assert job in needs(aggregate)
        called = load(ROOT / '.github/workflows' / (filename+'.yml'))
        assert set(events(called)) == {'workflow_call'}
        assert called['env']['SOURCE_COMMIT'] == '${{ inputs.source_commit }}'
        checkouts = [step for step in steps(called) if action(step, 'actions/checkout')]
        assert all(step.get('with', {}).get('ref') == '${{ inputs.source_commit }}' for step in checkouts)
        assert '$GITHUB_SHA' not in commands(called) and 'github.sha' not in str(called)
    assert any(step.get('if') == "always() && steps.features.outcome == 'success'" for step in aggregate['steps'])


def test_release_feature_gate_executes_the_tested_helper():
    workflow = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    assert 'run: python candidate-source/scripts/release_features.py gate' in workflow
    assert 'NEEDS_JSON: ${{ toJSON(needs) }}' in workflow
