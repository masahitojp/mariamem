"""Keep the CI publication boundary fail-closed without executing remote writes."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ci_release_summary import publication_rows


def test_publication_job_gate_and_handoff():
    workflow = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    before, publication = workflow.split('\n  publication:\n')
    assert 'default: verify' in before
    assert "if: always() && !cancelled() && inputs.operation == 'release' && needs.resolve.result == 'success' && needs.aggregate.result == 'success'" in publication
    assert 'contents: write' not in before and 'contents: write' in publication
    assert 'cancel-in-progress: false' in publication
    assert 'environment:' not in publication
    assert 'release_generated_ci.py restore' in publication
    assert 'release_generated_ci.py guard' in publication
    assert '--ready candidate-source/build/release/ci-ready.json' in publication
    assert 'config user.name' in publication and 'args+=(--dry-run)' not in publication
    assert 'options: [verify, release, public-smoke-recovery]' in before
    assert "if: always() && !cancelled() && inputs.operation == 'release' && needs.resolve.result == 'success' && needs.publication.result == 'success'" in publication
    assert 'build_alpha.py' not in publication and 'build_generated_guest.py' not in publication
    assert 'release-candidate-${{ matrix.platform }}-' in before
    assert 'release-evidence-${{ matrix.platform }}-' in before
    assert 'build_generated_guest.py --repetitions 2' in before
    assert 'regenerate_release_guest.py' in before
    assert 'compile_guest_aot.py' not in workflow and 'package_native.py' not in workflow
    assert 'build_alpha.py --ci-candidate\n' in before
    assert 'build_alpha.py --ci-candidate \\' not in before
    assert 'ubuntu-24.04-arm' in before
    assert 'generated_release_acceptance.py' in before
    for platform, runner in [('darwin-arm64', 'macos-15'), ('ubuntu24.04-x86_64', 'ubuntu-24.04')]:
        assert f'platform: {platform}' in before and f'runner: {runner}' in before
        assert f'platform: {platform}' in publication


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
    import re
    workflow = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    aggregate = workflow.split('\n  aggregate:\n', 1)[1].split('\n  publication:', 1)[0]
    for job, filename in FEATURES.items():
        # Match the job through its indented fields, up to the next job.
        caller = re.search(r'^  '+job+r':\n(.*?)(?=^  \S|\Z)', workflow, re.M | re.S)[1]
        assert 'needs: resolve' in caller
        assert 'uses: ./.github/workflows/'+filename+'.yml' in caller
        assert 'source_commit: ${{ needs.resolve.outputs.source_sha }}' in caller
        assert job in aggregate.split('    steps:', 1)[0]
        called = (ROOT / '.github/workflows' / (filename+'.yml')).read_text()
        triggers = called.split('permissions:', 1)[0]
        assert re.findall(r'^  ([a-z_]+):', triggers, re.M) == ['workflow_call']
        assert 'SOURCE_COMMIT: ${{ inputs.source_commit }}' in called
        for checkout in re.findall(r'- uses: actions/checkout@[^\n]+\n(.*?)(?=      - |\Z)', called, re.S):
            assert 'ref: ${{ inputs.source_commit }}' in checkout
        assert '$GITHUB_SHA' not in called and 'github.sha' not in called
    assert "if: always() && steps.features.outcome == 'success'" in aggregate


def test_actual_release_feature_gate_rejects_each_incomplete_result():
    import os
    import subprocess
    import textwrap
    workflow = (ROOT / '.github/workflows/release-candidate-ready.yml').read_text()
    script = textwrap.dedent(workflow.split("python - <<'PYGATE'\n", 1)[1].split('          PYGATE', 1)[0])
    good = {job: {'result': 'success'} for job in FEATURES}
    def run(needs):
        return subprocess.run([sys.executable, '-c', script],
                              env=dict(os.environ, NEEDS_JSON=json.dumps(needs)),
                              capture_output=True).returncode
    assert run(good) == 0
    for job in FEATURES:
        for result in ['failure', 'cancelled', 'skipped', None]:
            needs = dict(good)
            if result is None:
                del needs[job]
            else:
                needs[job] = {'result': result}
            assert run(needs) != 0, (job, result)
