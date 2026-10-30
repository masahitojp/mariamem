"""E2E boundary selection; full manual acceptance always selects every family."""
import argparse
import json
import os

FAMILIES = ('e2e',)
E2E_FILES = {'python/mariamem/e2e.py', 'mariamemtest/http.go',
             'scripts/e2e_installed.py', 'scripts/e2e_workflow_timing.py',
             'tests/test_e2e_entry.py', 'tests/test_e2e_decision.py',
             'tests/test_e2e_installed.py', 'scripts/live_selection.py',
             'scripts/live_ci.py', 'tests/test_live_selection.py',
             'tests/test_live_ci_workflow.py', '.github/workflows/live-host.yml'}


def select(paths, event, reason='local changed-input classification'):
    if event != 'pull_request' or not paths or reason not in (
            'local changed-input classification', 'unknown/runtime input'):
        return dict.fromkeys(FAMILIES, True)
    for path in paths:
        if path in E2E_FILES or path.startswith(('docs/examples/e2e_owned/', 'mariamemtest/http_')):
            return {'e2e': True}
        if path.endswith('.md') and not path.startswith('docs/examples/'):
            continue
        if path.startswith(('tests/fixture_entry_acceptance/', 'tests/preparation_migration_acceptance/')) or path in (
                'python/mariamem/pytest_plugin.py', 'python/mariamem/preparation.py',
                'mariamemtest/fixture.go', 'mariamemtest/fixture_test.go',
                'mariamemtest/campaign_test.go', 'mariamemtest/physical_test.go'):
            continue
        # Shared SDK/runtime/build inputs and unknown files stay conservative.
        return {'e2e': True}
    return {'e2e': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--github-output', action='store_true')
    args = parser.parse_args()
    # #34 deliberately removed automatic full-acceptance diffs. Do not revive
    # that policy here: the manual event selects all, independently of prose.
    result = select([], os.environ.get('GITHUB_EVENT_NAME', 'unknown'))
    print(json.dumps(result))
    if args.github_output:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            for key, value in result.items():
                output.write(key+'='+str(value).lower()+'\n')


if __name__ == '__main__':
    main()
