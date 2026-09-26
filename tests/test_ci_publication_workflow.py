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
    assert "if: inputs.operation != 'verify' && needs.verification.result == 'success'" in publication
    assert 'contents: write' not in before
    assert 'contents: write' in publication
    assert 'cancel-in-progress: false' in publication
    assert 'environment:' not in publication  # no second approval gate
    assert '--mode guard-only' in publication
    assert 'ref: ${{ needs.resolve.outputs.source_sha }}' in publication
    assert 'ready-input/build/release/SHA256SUMS' in publication
    assert 'ready-input/build/release/ci-ready.json' in publication
    assert 'config user.name' in publication
    assert 'args+=(--dry-run)' in publication
    assert "if: inputs.operation == 'release'" in publication
    assert 'ci-public-smoke-consumer.log' in publication
    assert 'build_alpha.py' not in publication and 'build_guest' not in publication


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
