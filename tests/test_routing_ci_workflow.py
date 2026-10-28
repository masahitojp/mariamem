"""Routing's dedicated matrix must survive delegation of the generic source job."""
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT/'.github/workflows/connection-routing.yml'
sys.path.insert(0, str(ROOT/'scripts'))


def job(text, name):
    return re.search(r'^  '+name+r':\n(.*?)(?=^  \S|\Z)', text.split('jobs:\n', 1)[1], re.M | re.S)[1]


def native_selected(text, scope, compatibility, source, delegated, cancelled=False):
    block = job(text, 'native')
    expression = block.split('    if: >-\n', 1)[1].split('    strategy:', 1)[0].strip()
    assert expression.startswith('${{') and expression.endswith('}}')
    expression = expression[3:-2].replace('!cancelled()', repr(not cancelled))
    for key, value in [('needs.scope.result', scope), ('needs.compatibility.result', compatibility),
                       ('needs.source.result', source), ('needs.scope.outputs.ubuntu_check', delegated)]:
        expression = expression.replace(key, repr(value))
    expression = ' '.join(expression.replace('&&', 'and').replace('||', 'or').split())
    return eval(expression, {'__builtins__': {}})


def test_source_delegation_preserves_native_and_compatibility():
    from test_live_ci_workflow import validate_development_owners
    from development_scope import canonical_plan, select
    text = WORKFLOW.read_text()
    validate_development_owners((ROOT/'.github/workflows/check.yml').read_text())
    assert 'needs: scope' in job(text, 'source')
    assert "if: needs.scope.outputs.ubuntu_check != 'false'" in job(text, 'source')
    assert 'python scripts/verify.py check' in job(text, 'source')
    assert "python scripts/development_scope.py --candidate-sha '${{ github.sha }}' --github-output" in job(text, 'scope')
    assert 'fetch-depth: 0' in job(text, 'scope')
    assert 'ubuntu_check: ${{ steps.diff.outputs.ubuntu_check }}' in job(text, 'scope')
    assert 'needs: [scope, compatibility, source]' in job(text, 'native')
    assert 'os: [macos-15, ubuntu-24.04]' in job(text, 'native')
    assert "python: '3.11'" in job(text, 'compatibility') and "python: '3.14'" in job(text, 'compatibility')
    assert 'tests/routing_acceptance/run.py' in job(text, 'native')
    assert '  workflow_dispatch:' in text and 'pull_request_target:' not in text
    assert 'pull_request.head.sha' not in text and 'ref:' not in text
    full = select(['python/mariamem/routing.py'])
    assert canonical_plan(full, 'push', 'refs/heads/main')['ubuntu_check'] is False
    assert canonical_plan(full, 'workflow_dispatch', 'refs/heads/main')['ubuntu_check'] is True
    assert canonical_plan(full, 'push', 'refs/heads/feat/connection-routing')['ubuntu_check'] is True
    assert canonical_plan(select([], fallback='event diff unavailable; full verification'),
                          'push', 'refs/heads/main')['ubuntu_check'] is True
    assert canonical_plan(select(['scripts/development_scope.py']),
                          'push', 'refs/heads/main')['ubuntu_check'] is True


@pytest.mark.parametrize('scope,compatibility,source,delegated,cancelled,expected', [
    ('success', 'success', 'success', 'true', False, True),
    ('success', 'success', 'skipped', 'false', False, True),
    ('success', 'success', 'skipped', 'true', False, False),
    ('success', 'success', 'skipped', None, False, False),
    ('success', 'success', 'failure', 'false', False, False),
    ('failure', 'success', 'skipped', 'false', False, False),
    ('success', 'failure', 'skipped', 'false', False, False),
    ('success', 'cancelled', 'success', 'true', False, False),
    ('success', 'success', 'success', 'true', True, False),
])
def test_native_gate_rejects_failures_but_accepts_intentional_source_skip(scope, compatibility, source, delegated, cancelled, expected):
    assert native_selected(WORKFLOW.read_text(), scope, compatibility, source, delegated, cancelled) is expected
