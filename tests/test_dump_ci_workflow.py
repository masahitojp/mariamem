"""Trigger coverage and exact-checkout execution contracts for the dump CI owner."""
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
WORKFLOW = ROOT/'.github/workflows/dump-import-productization.yml'
RELEVANT = [
    '.github/workflows/dump-import-productization.yml',
    'tests/dump_import_acceptance/run.py', 'tests/test_dump_ci_workflow.py',
    'tests/preparation_migration_acceptance/migrations/versions/m1_initial.py',
    'tests/test_git_identity.py', 'scripts/git_identity.py', 'scripts/build_alpha.py',
    'python/mariamem/dump.py', 'python/setup.cfg', 'internal/control/host.go',
    'internal/guest/guest.go', 'internal/generatedgo/main.go',
    'cmd/mariamem-host/main.go', 'guest/source.patch',
    'release/generated-go-inputs.json', 'go.mod', 'go.sum', 'mariamem.go',
]


def selected(path, pattern):
    # GitHub's * does not cross path separators; this workflow uses only * and **.
    expression = re.escape(pattern).replace(r'\*\*', 'DOUBLE_STAR').replace(r'\*', '[^/]*').replace('DOUBLE_STAR', '.*')
    return re.fullmatch(expression, path) is not None


def test_path_selection_does_not_treat_root_go_glob_as_all_runtime_files():
    assert selected('mariamem.go', '*.go')
    assert not selected('internal/guest/guest.go', '*.go')
    assert selected('internal/guest/guest.go', 'internal/**')


def validate_triggers(text):
    # Deliberately enforce the simple explicit workflow syntax (no YAML aliases).
    # GitHub owns actual YAML execution; these are selection-contract mutations.
    for event in ['push', 'pull_request']:
        match = re.search(r'^  '+event+r':\n(.*?)(?=^  \S|^\S)', text, re.M | re.S)
        assert match, event+' trigger missing'
        block = match[1]
        branches = re.search(r'^    branches: \[([^]]+)\]$', block, re.M)
        assert branches and 'main' in [b.strip() for b in branches[1].split(',')]
        patterns = re.findall(r"^      - '([^']+)'$", block, re.M)
        for path in RELEVANT:
            assert any(selected(path, pattern) for pattern in patterns), path+' unselected'
    assert '  workflow_dispatch:' in text
    assert 'pull_request_target:' not in text
    assert 'permissions:\n  contents: read' in text


def test_main_and_pull_request_cover_all_dump_dependencies():
    validate_triggers(WORKFLOW.read_text())


@pytest.mark.parametrize('original,replacement', [
    ('  pull_request:', '  retired_pull_request:'),
    ('branches: [main]', 'branches: [unused]'),
    ("      - 'tests/preparation_migration_acceptance/**'\n", ''),
    ("      - 'internal/**'\n", ''),
    ("      - 'scripts/**'\n", ''),
    ("      - 'python/**'\n", ''),
])
def test_trigger_mutations_are_detected(original, replacement):
    with pytest.raises(AssertionError):
        validate_triggers(WORKFLOW.read_text().replace(original, replacement))


def test_matrix_uses_tested_checkout_not_pr_head_override():
    text = WORKFLOW.read_text()
    assert 'pull_request.head.sha' not in text and 'ref:' not in text
    assert '--expected-source-commit "$GITHUB_SHA"' in text
    assert 'runs-on: ${{ matrix.os }}' in text  # Event-specific OS selection is tested in test_ci_efficiency.
    for script in ['campaign.py', 'run.py']:
        source = (ROOT/'tests/dump_import_acceptance'/script).read_text()
        assert 'verify_go_binary(' in source and 'source_identity(' in source
    assert 'tests/test_git_identity.py' in text


def validate_canonical_ownership(text, development):
    from test_live_ci_workflow import validate_development_owners
    validate_development_owners(development)
    assert "python scripts/development_scope.py --candidate-sha '${{ github.sha }}' --github-output" in text
    assert 'fetch-depth: 0' in text
    for job, output, command in [
        ('development-checks', 'ubuntu_check', 'check'),
        ('development-integration', 'ubuntu_integration', 'integration'),
    ]:
        match = re.search(r'^  '+job+r':\n(.*?)(?=^  \S|\Z)', text, re.M | re.S)
        assert match, job
        block = match[1]
        assert 'needs: scope' in block
        assert 'runs-on: ubuntu-24.04' in block
        assert "if: needs.scope.outputs.run_runtime == 'true' && needs.scope.outputs."+output+" != 'false'" in block
        assert 'python scripts/verify.py '+command in block
        assert output+': ${{ steps.diff.outputs.'+output+' }}' in text
    # Selected Dump-specific oracles are independent of canonical delegation.
    assert re.search(r"^  native-reference:\n    needs: scope\n    if: needs.scope.outputs.run_runtime == 'true'\n    runs-on:", text, re.M)
    assert 'run_runtime: ${{ steps.diff.outputs.run_runtime }}' in text
    assert 'needs: native-reference' in text
    for owner in ['producer.py', 'native_reference.py', 'variant.py', 'campaign.py']:
        assert 'tests/dump_import_acceptance/'+owner in text


def test_dump_delegation_keeps_canonical_and_specific_owners():
    validate_canonical_ownership(WORKFLOW.read_text(), (ROOT/'.github/workflows/check.yml').read_text())


@pytest.mark.parametrize('before,after', [
    ('needs: scope', 'needs: []'),
    ("if: needs.scope.outputs.run_runtime == 'true' && needs.scope.outputs.ubuntu_check != 'false'", "if: false"),
    ("if: needs.scope.outputs.run_runtime == 'true' && needs.scope.outputs.ubuntu_integration != 'false'", "if: false"),
    ('steps.diff.outputs.ubuntu_check', 'steps.diff.outputs.missing'),
    ('python scripts/verify.py check', 'echo omitted-check'),
    ('python scripts/verify.py integration', 'echo omitted-integration'),
    ('needs: native-reference', 'needs: []'),
    ('tests/dump_import_acceptance/campaign.py', 'unbound-campaign'),
])
def test_dump_delegation_regressions_are_detected(before, after):
    text = WORKFLOW.read_text()
    assert before in text
    with pytest.raises(AssertionError):
        validate_canonical_ownership(text.replace(before, after), (ROOT/'.github/workflows/check.yml').read_text())


@pytest.mark.parametrize('before,after', [
    ('runs-on: ubuntu-latest', 'runs-on: macos-15'),
    ('runs-on: ubuntu-24.04', 'runs-on: macos-15'),
    ('python scripts/verify.py integration', 'echo omitted-integration'),
    ("check --scope '${{ needs.scope.outputs.check_scope }}'", 'check --scope docs'),
    ('    branches: [main]', '    branches: [main]\n    paths: [docs/**]'),
])
def test_dump_cannot_delegate_to_a_missing_development_owner(before, after):
    development = (ROOT/'.github/workflows/check.yml').read_text()
    assert before in development
    with pytest.raises(AssertionError):
        validate_canonical_ownership(WORKFLOW.read_text(), development.replace(before, after))
