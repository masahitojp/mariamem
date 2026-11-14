"""Routing campaign has one release owner, not a second daily integration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_routing_release_keeps_compatibility_and_both_platforms():
    from workflow_model import load, commands, needs
    route = load(ROOT/'.github/workflows/connection-routing.yml')
    release = load(ROOT/'.github/workflows/release-candidate-ready.yml')
    assert 'tests/test_routing.py tests/test_routing_pytest.py tests/test_routing_receipts.py' in commands(release)
    assert any(needs(job) == {'resolve', 'runtime', 'units'} for job in release['jobs'].values())
    assert 'compatibility' not in route['jobs']
    assert any(job.get('strategy', {}).get('matrix', {}).get('os') == ['macos-15', 'ubuntu-24.04'] for job in route['jobs'].values())
    assert 'tests/routing_acceptance/run.py' in commands(route)
    assert 'scripts/verify.py' not in commands(route)
    assert 'tests/routing_acceptance/run.py' not in (ROOT/'scripts/verify.py').read_text()
