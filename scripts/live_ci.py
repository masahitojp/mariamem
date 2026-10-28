#!/usr/bin/env python3
"""Always report a Live required check; skip only an explicit guide-only diff."""
import argparse
import json
import os
from pathlib import Path

from development_scope import boundary, event_base, plan

ROOT = Path(__file__).resolve().parents[1]


def required(paths, reason):
    """Skip the expensive matrix only for a diff the selector calls documentation.

    The required check must still report, so the scope and gate jobs always run;
    only the native, Live and installed jobs are skipped. Any non-documentation
    path (including unknown documentation-directory inputs) keeps the full matrix.
    """
    return (
        reason != 'local changed-input classification'
        or not paths
        or any(boundary(path) != 'docs' for path in paths)
    )


def canonical_plan(plan, event, ref):
    """Delegate only checks owned by Development for this same event/source."""
    shared = (event == 'pull_request' or (event == 'push' and ref == 'refs/heads/main'))
    shared = shared and plan.get('reason') in {
        'local changed-input classification', 'unknown/runtime input',
    }
    return {
        'ubuntu_check': not (shared and plan.get('check_scope') == 'full'),
        'macos_integration': not (shared and plan.get('integration') is True),
    }


def verify_gate(needs):
    assert set(needs) == {'scope', 'native-reference', 'live'}, 'missing dependency'
    scope = needs['scope']
    assert scope['result'] == 'success', 'scope did not succeed'
    selected = scope['outputs'].get('run_live')
    assert selected in ('true', 'false'), 'invalid scope output'
    expected = 'success' if selected == 'true' else 'skipped'
    for job in ['native-reference', 'live']:
        assert needs[job]['result'] == expected, job + ' did not finish as required'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    scope = sub.add_parser('scope')
    scope.add_argument('--candidate-sha', required=True)
    scope.add_argument('--github-output', action='store_true')
    sub.add_parser('gate')
    args = parser.parse_args()
    if args.operation == 'gate':
        verify_gate(json.loads(os.environ['NEEDS_JSON']))
        print('PASS: Live required gate')
        return
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    result = plan(ROOT, args.candidate_sha, event_base(event, os.environ['GITHUB_EVENT_NAME']))
    result['run_live'] = required(result['changed_paths'], result['reason'])
    result.update(canonical_plan(result, os.environ['GITHUB_EVENT_NAME'], os.environ.get('GITHUB_REF')))
    print(json.dumps(result, indent=2))
    if args.github_output:
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
            output.write('run_live=' + str(result['run_live']).lower() + '\n')
            for key in ['ubuntu_check', 'macos_integration']:
                output.write(key + '=' + str(result[key]).lower() + '\n')


if __name__ == '__main__':
    main()
