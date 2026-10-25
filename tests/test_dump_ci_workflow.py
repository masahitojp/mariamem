"""Trigger coverage and exact-checkout execution contracts for the dump CI owner."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
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
    assert 'os: [ubuntu-24.04, macos-15]' in text
    for script in ['campaign.py', 'run.py']:
        source = (ROOT/'tests/dump_import_acceptance'/script).read_text()
        assert 'verify_go_binary(' in source and 'source_identity(' in source
    assert 'tests/test_git_identity.py' in text
