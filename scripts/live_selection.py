"""Conservative PR-only selection; unknown inputs retain every acceptance family."""
FAMILIES = ('mac_integration', 'g1', 'live_runtime', 'examples', 'installed', 'p1')

def select(paths, event, reason):
    full = dict.fromkeys(FAMILIES, True)
    if event != 'pull_request' or not paths or reason not in (
            'local changed-input classification', 'unknown/runtime input'):
        return full
    selected = set()
    for path in paths:
        if path.startswith('docs/') and path.endswith('.md') and not path.startswith('docs/examples/'):
            continue
        if path in (
                'python/mariamem/_prepare.py', 'python/mariamem/_pytest_owner.py',
                'tests/test_prepare_command.py', 'tests/test_p1_pytest_entry.py',
                'tests/test_p1_runtime.py', 'tests/test_p1_native_control.py',
                'tests/fixture_entry_acceptance/p1_migrate.py',
                'tests/fixture_entry_acceptance/native.py',
                'tests/fixture_entry_acceptance/time_campaign.py'):
            selected.update(('p1', 'installed'))
        elif path.startswith('tests/fixture_entry_acceptance/'):
            # Shared fixture inputs may affect both Go and Python campaigns.
            selected.update(('g1', 'p1', 'installed'))
        elif path in (
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
            selected.update(('mac_integration', 'live_runtime', 'examples', 'installed', 'p1'))
        elif path in ('python/mariamem/pytest_plugin.py',):
            # Preserve existing integration/Live consumers alongside P1 acceptance.
            selected.update(('mac_integration', 'live_runtime', 'examples', 'installed', 'p1'))
        else:
            return full
    return {name: name in selected for name in FAMILIES}
