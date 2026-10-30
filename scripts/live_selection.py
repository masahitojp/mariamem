"""Conservative PR-only selection; unknown inputs retain every acceptance family."""
from development_scope import boundary

FAMILIES = ('mac_integration', 'g1', 'live_runtime', 'examples', 'installed')

def select(paths, event, reason):
    full = dict.fromkeys(FAMILIES, True)
    if event != 'pull_request' or not paths or reason not in (
            'local changed-input classification', 'unknown/runtime input'):
        return full
    selected = set()
    for path in paths:
        if boundary(path) == 'docs':
            continue
        if path.startswith('tests/fixture_entry_acceptance/') or path in (
                'mariamemtest/fixture.go', 'mariamemtest/fixture_test.go',
                'mariamemtest/physical_test.go', 'mariamemtest/campaign_test.go',
                'scripts/go_fixture_campaign.py', 'scripts/go_fixture_completion.py',
                'tests/test_go_fixture_campaign.py', 'tests/test_go_fixture_completion.py',
                'tests/gointegration/fixture_test.go'):
            selected.update(('g1', 'installed'))
        elif path.startswith(('internal/live/', 'internal/control/', 'tests/live_acceptance/',
                              'tests/e2e_native_control/', 'docs/examples/live/')) or path in (
                'live.go', 'live_test.go', 'python/mariamem/live.py',
                'tests/test_live_unit.py', 'tests/test_live_oracles.py'):
            selected.update(('live_runtime', 'examples', 'installed'))
        elif path in ('python/mariamem/routing.py', 'python/mariamem/_routing_drivers.py',
                      'python/mariamem/_routing_sqlalchemy.py') or path.startswith('tests/routing_acceptance/'):
            selected.update(('mac_integration', 'live_runtime', 'examples', 'installed'))
        elif path in ('python/mariamem/pytest_plugin.py',):
            # Keep Python/runtime acceptance until the dedicated P1 campaign is on main.
            selected.update(('mac_integration', 'live_runtime', 'examples', 'installed'))
        else:
            return full
    return {name: name in selected for name in FAMILIES}
