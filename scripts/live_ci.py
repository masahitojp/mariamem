#!/usr/bin/env python3
"""Always report a Live required check; skip only an explicit documentation diff."""
import argparse
import json
import os
from pathlib import Path

from live_selection import FAMILIES, select as select_families

from development_scope import boundary, canonical_plan, event_base, plan

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


def selected_live(paths, reason, draft):
    """Draft pull requests and documentation-only diffs skip the expensive matrix.

    A draft cannot be merged, so paying for native, browser and installed jobs
    there only delays ready pull requests on the shared macOS runners. Marking the
    pull request ready for review starts a fresh run with the full matrix.
    """
    if draft:
        return False
    return required(paths, reason)


def verify_gate(needs):
    assert set(needs) == {'scope', 'native-reference', 'live'}, 'missing dependency'
    scope = needs['scope']
    assert scope['result'] == 'success', 'scope did not succeed'
    draft = scope['outputs'].get('pull_request_draft')
    assert draft in ('true', 'false'), 'missing draft status'
    assert draft == 'false', 'Draft: Live deferred; mark ready for required validation'
    selected = scope['outputs'].get('run_live')
    assert selected in ('true', 'false'), 'invalid scope output'
    if selected == 'true':
        flags = [scope['outputs'].get(key) for key in FAMILIES]
        assert all(flag in ('true', 'false') for flag in flags), 'missing family selection'
        assert 'true' in flags, 'empty selected acceptance'
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
    draft = (os.environ['GITHUB_EVENT_NAME'] == 'pull_request'
             and bool(event.get('pull_request', {}).get('draft')))
    result['pull_request_draft'] = draft
    result['run_live'] = selected_live(result['changed_paths'], result['reason'], draft)
    result['run_live_reason'] = ('draft pull request' if draft else
                                 'documentation only' if not result['run_live'] else 'selected')
    result.update(canonical_plan(result, os.environ['GITHUB_EVENT_NAME'], os.environ.get('GITHUB_REF')))
    result.update(select_families(result["changed_paths"], os.environ["GITHUB_EVENT_NAME"], result["reason"]))
    print(json.dumps(result, indent=2))
    if args.github_output:
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
            output.write('run_live=' + str(result['run_live']).lower() + '\n')
            output.write('pull_request_draft=' + str(draft).lower() + '\n')
            for key in ['ubuntu_check', 'ubuntu_integration', *FAMILIES]:
                output.write(key + '=' + str(result[key]).lower() + '\n')


if __name__ == '__main__':
    main()
