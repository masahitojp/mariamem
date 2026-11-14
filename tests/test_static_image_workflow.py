"""Candidate gate keeps both page-size platforms, source binding and runtime checks."""
from pathlib import Path


def test_static_image_candidate_boundaries():
    root = Path(__file__).resolve().parents[1]
    from workflow_model import load, commands, steps, events, action
    model = load(root/'.github/workflows/issue123-layout.yml')
    text = commands(model)
    assert any(job.get('strategy', {}).get('matrix', {}).get('runner') == ['macos-15', 'ubuntu-24.04'] for job in model['jobs'].values())
    assert any(action(step, 'actions/setup-go') and step['with']['go-version'] == '1.26.10' for step in steps(model))
    assert any(step.get('with', {}).get('if-no-files-found') == 'error' for step in steps(model))
    for contract in (
        'scripts/git_identity.py inspect HEAD', 'os.environ["GITHUB_SHA"]',
        'test -z "$(git status --porcelain)"', 'go clean -testcache',
        './internal/generatedgo/layoutgen -check',
        'scripts/verify_generated_runtime.py', 'tests/test_runtime_static_image.py',
        './internal/generatedgo/image', 'scripts/verify.py smoke',
        './tests/gointegration ./tests/godefault ./tests/generatedmemory',
        './tests/generatedmemory -run=TestProcessImageSurvivesIndependentRootsAndSnapshots',
        'tests/test_consumer_acceptance.py',
        'tests/test_owned_snapshot.py', 'tests/snapshots.py',
        'SHA256SUMS.json',
    ):
        assert contract in text
    assert 'operation: release' not in text and 'continue-on-error' not in text
    assert 'workflow_dispatch' in events(model) and not set(events(model)) & {'push', 'pull_request'}
    assert all('continue-on-error' not in owner for owner in [*model['jobs'].values(), *steps(model)])
