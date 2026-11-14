"""Local diff selection cannot depend on historical Product artifact lifetime."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import development_scope as scope
import verify


@pytest.mark.parametrize('path', [
    'README.md', 'AGENTS.md', 'docs/development.md', 'docs/reviews/measurement.md',
    'benchmarks/fast-tranche-baseline.md', 'release/NOTES-v0.4.6-draft.md',
])
def test_documentation_needs_no_runtime_receipt(path):
    assert scope.select([path])['check_scope'] == 'docs'
    assert not scope.select([path])['integration']


@pytest.mark.parametrize('runtime', [
    'release/NOTES-v0.6.2.md', 'release/generated-go-inputs.json',
    'benchmarks/new-report.md', 'benchmarks/fast-tranche-baseline.py',
    'mariamem.go',
])
def test_historical_doc_cleanup_keeps_active_and_unknown_inputs_conservative(runtime):
    result = scope.select(['release/NOTES-v0.4.6-draft.md',
                           'benchmarks/fast-tranche-baseline.md', runtime])
    assert result['check_scope'] == 'full' and result['integration']


def test_policy_review_pr_skips_runtime_checks():
    paths = ['AGENTS.md', 'docs/development.md', 'docs/project-status.md']
    result = scope.select(paths)
    assert result['check_scope'] == 'docs'
    assert not result['integration']



@pytest.mark.parametrize('path', [
    'benchmarks/README.md',
    'docs/benchmarks/go126-vs-go127-evidence/raw/fixture-fresh-00-1268.json',
    'docs/benchmarks/go126-vs-go127-evidence/statistics.csv',
    'docs/benchmarks/go126-vs-go127-evidence/profile-1268-fresh-alloc-top.txt',
    'docs/benchmarks/go126-vs-go127-evidence/SHA256SUMS',
    'docs/reviews/memfs-discovery-evidence/inputs.json',
])
def test_archived_measurement_data_is_documentation(path):
    assert scope.select([path])['check_scope'] == 'docs'
    assert not scope.select([path])['integration']


@pytest.mark.parametrize('name', ['build.py', 'profile.py', 'summarize.py'])
def test_known_reproduction_recipes_are_tooling(name):
    result = scope.select(['docs/benchmarks/go126-vs-go127-evidence/' + name])
    assert result['check_scope'] == 'python' and not result['integration']


@pytest.mark.parametrize('path', [
    'docs/new-evidence.json',
    'docs/benchmarks/go126-vs-go127-evidence/runtime.go',
    'docs/benchmarks/go126-vs-go127-evidence/new_helper.py',
    'docs/reviews/memfs-discovery-evidence/guest.wasm',
    'docs/benchmarks/go126-vs-go127-evidence-other/inputs.json',
])
def test_evidence_scope_does_not_exempt_unknown_code_or_directories(path):
    result = scope.select([path])
    assert result['check_scope'] == 'full' and result['integration']


@pytest.mark.parametrize('path', [
    'scripts/experiment_workspace.py', 'scripts/generated_release_acceptance.py',
    'scripts/release_generated_ci.py', 'scripts/validate_product_candidate.py',
    'tests/consumer/run_sqlalchemy.py', 'tests/consumer/run_gorm.py',
    'tests/verify_alpha.py', '.github/workflows/v044-product-validation.yml', 'scripts/runtime_validation.py',
    'tests/test_runtime_validation.py', '.github/workflows/check.yml',
    '.agents/skills/experiment-workspace/SKILL.md',
    '.agents/skills/review/SKILL.md',
])
def test_tooling_remains_checked_without_runtime_qualification(path):
    assert scope.select([path])['check_scope'] == 'python'
    assert not scope.select([path])['integration']


def test_wasix_guard_metadata_selects_source_checks_only():
    result = scope.select(['release/wasix-host-stubs.json',
                           'tests/test_generated_runtime_inventory.py'])
    assert result['check_scope'] == 'python' and not result['integration']
    for runtime in ['internal/generatedgo/main.go', 'scripts/generate_runtime.py',
                    'release/generated-go-inputs.json', 'release/new-contract.json']:
        assert scope.select(['release/wasix-host-stubs.json', runtime])['integration']


@pytest.mark.parametrize('path', [
    'internal/generatedgo/code/base/owned_prepared.go', 'snapshot.go',
    'python/mariamem/__init__.py', 'python/mariamem/pytest_plugin.py',
    'guest/source.patch', 'guest/inputs.json', 'go.mod',
    'scripts/generate_runtime.py', 'scripts/build_alpha.py',
    'scripts/verify.py', 'tests/test_python_wire.py', 'tests/support/wire_acceptance.py',
    'tests/gointegration/lifecycle_test.go', 'tests/consumer/test_sqlalchemy_dogfood.py',
    'new-unknown-input.json', 'scripts/new_helper.py', 'tests/test_new_guest_case.py', '../README.md',
])
def test_runtime_and_unknown_changes_do_not_silently_downgrade(path):
    result = scope.select(['docs/development.md', path])
    assert result['check_scope'] == 'full' and result['integration']


def test_missing_or_empty_diff_is_conservative():
    assert scope.select([])['integration']
    assert scope.event_base({'before': 'a'}, 'push') == 'a'
    assert scope.event_base({'pull_request': {'base': {'sha': 'b'}}}, 'pull_request') == 'b'
    assert scope.event_base({}, 'workflow_dispatch') is None


@pytest.fixture
def git_repo(tmp_path):
    root = tmp_path / 'synthetic-git'
    root.mkdir()
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'Test fixture')
    git('config', 'user.email', 'test@example.invalid')
    (root / 'README.md').write_text('old\n')
    git('add', '.')
    git('commit', '-qm', 'baseline')
    base = git('rev-parse', 'HEAD')
    yield root, git, base
    # This nested repository is explicitly test-owned synthetic history, not
    # user source to park indefinitely in workspace cleanup REVIEW.
    shutil.rmtree(root)


def test_event_diff_uses_local_commits_not_receipts_or_network(git_repo, monkeypatch):
    root, git, base = git_repo
    (root / 'release').mkdir()
    (root / 'release/runtime-validation.json').write_text('{"expired":true}')
    (root / 'README.md').write_text('new\n')
    git('add', 'README.md')
    git('commit', '-qm', 'docs')
    candidate = git('rev-parse', 'HEAD')
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    result = scope.plan(root, candidate, base)
    assert result['changed_paths'] == ['README.md']
    assert result['check_scope'] == 'docs' and not result['integration']
    (root / 'release/runtime-validation.json').unlink()
    assert scope.plan(root, candidate, base) == result
    assert scope.plan(root, candidate, '0' * 40)['integration']
    assert scope.plan(root, candidate, 'f' * 40)['integration']
    git('tag', '-a', 'v0.4.4', '-m', 'annotated fixture')
    tag = git('rev-parse', 'v0.4.4')
    with pytest.raises(ValueError, match='tag object'):
        scope.plan(root, tag, base)


def test_rename_out_of_runtime_does_not_hide_deleted_input(git_repo):
    root, git, base = git_repo
    (root / 'runtime.go').write_text('package fixture\n')
    git('add', '.')
    git('commit', '-qm', 'runtime')
    base = git('rev-parse', 'HEAD')
    git('mv', 'runtime.go', 'removed.md')
    git('commit', '-qm', 'rename')
    result = scope.plan(root, git('rev-parse', 'HEAD'), base)
    assert 'runtime.go' in result['changed_paths'] and result['integration']


@pytest.mark.parametrize('kind', ['docs', 'python'])
def test_narrow_checks_do_not_build_guest_or_consume_release_receipts(monkeypatch, kind):
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append((argv, kw)))
    monkeypatch.setenv('MARIAMEM_TEST_HOST', 'must-not-start')
    verify.check(kind)
    assert all(argv[0] != 'go' for argv, _ in calls)
    assert all('runtime_validation.py' not in ' '.join(argv) for argv, _ in calls)
    pytest_calls = [(a, kw) for a, kw in calls if 'pytest' in a]
    assert bool(pytest_calls) == (kind == 'python')
    for _, kw in pytest_calls:
        assert 'MARIAMEM_TEST_HOST' not in kw['env']


def test_workflow_has_no_external_runtime_receipt_dependency():
    text = (ROOT / '.github/workflows/check.yml').read_text()
    assert 'scripts/development_scope.py' in text
    assert 'runtime_validation.py' not in text and 'GITHUB_TOKEN' not in text
    assert 'actions: read' not in text
    assert 'fetch-depth: 0' in text
    assert "if: steps.diff.outputs.integration == 'true'" in text
    assert "check --scope '${{ steps.diff.outputs.check_scope }}'" in text


def test_source_guarantees_run_before_compilation_exactly_once(monkeypatch):
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append(argv))
    monkeypatch.setattr(verify.subprocess, 'check_output', lambda *a, **kw: '/toolchain\n')
    verify.check()
    early = next(a for a in calls if 'pytest' in a)
    assert set(verify.SOURCE_TESTS) <= set(early)
    assert calls.index(early) < next(i for i,a in enumerate(calls) if a[0] == 'go')
    broad = next(a for a in calls if 'pytest' in a and 'tests' in a)
    assert 'tests' in broad
    assert {'--ignore='+p for p in verify.SOURCE_TESTS} <= set(broad)
    assert len(verify.SOURCE_TESTS) == len(set(verify.SOURCE_TESTS))
    import release_preparation_checks as preparation
    assert set(verify.SOURCE_TESTS) <= set(preparation.TESTS)
    assert len(preparation.TESTS) == len(set(preparation.TESTS))


@pytest.mark.parametrize('boundary', ['inventory', 'source_oracles'])
def test_source_failure_stops_before_any_go_execution(monkeypatch, boundary):
    calls = []
    def run(argv, **kw):
        calls.append(argv)
        if (boundary == 'inventory' and 'scripts/verify_generated_runtime.py' in argv or
                boundary == 'source_oracles' and set(verify.SOURCE_TESTS) <= set(argv)):
            raise RuntimeError('source boundary rejected')
    monkeypatch.setattr(verify, 'run', run)
    monkeypatch.setattr(verify.subprocess, 'check_output',
                        lambda *a, **kw: pytest.fail('Go environment queried after failure'))
    with pytest.raises(RuntimeError, match='source boundary rejected'):
        verify.check()
    assert all(a[0] != 'go' for a in calls)


@pytest.mark.parametrize('path', [
    'tests/test_ci_efficiency.py', 'tests/test_live_ci_workflow.py',
    'tests/test_ci_runtime_selection.py', 'tests/test_dump_ci_workflow.py',
    'tests/test_django_recipe_workflow.py', 'tests/test_routing_ci_workflow.py',
])
def test_known_ci_policy_tests_do_not_start_go(path):
    result = scope.select(['.github/workflows/check.yml', path])
    assert result['check_scope'] == 'python' and not result['integration']


def test_daily_product_checks_and_release_complete_checks_have_separate_owners(monkeypatch):
    monkeypatch.setattr(verify.subprocess, 'check_output', lambda *a, **kw: '/toolchain\n')
    for profile in ['daily', 'full']:
        calls = []
        monkeypatch.setattr(verify, 'run', lambda a, **kw: calls.append((a, kw)))
        verify.check(profile=profile)
        tests = next(a for a, _ in calls if a[:2] == ['go', 'test'])
        vet, options = next((a, kw) for a, kw in calls if a[:2] == ['go', 'vet'])
        assert options['env']['MARIAMEM_VET_PROFILE'] == profile
        assert '-vet=off' in tests
        if profile == 'daily':
            assert tests[-4:] == vet[-4:] == verify.DAILY_GO_PACKAGES
            assert '-vet=off' in tests and './...' not in tests
        else:
            assert tests[-1] == vet[-1] == './...'
        assert any('scripts/verify_generated_runtime.py' in a for a, _ in calls)


@pytest.mark.parametrize('path', sorted(scope.WORKFLOW_SCOPES))
def test_reviewed_workflow_only_changes_do_not_compile_runtime(path):
    result = scope.select([path])
    assert result['check_scope'] == 'python' and not result['integration']
    mixed = scope.select([path, 'mariamem.go'])
    assert mixed['check_scope'] == 'full' and mixed['integration']


def test_every_maintained_workflow_has_an_explicit_reviewed_scope():
    actual = {p.relative_to(ROOT).as_posix() for p in (ROOT/'.github/workflows').glob('*.yml')}
    assert actual == set(scope.WORKFLOW_SCOPES)
    assert set(scope.WORKFLOW_SCOPES.values()) <= {'python', 'runtime'}
    assert scope.select(['.github/workflows/new-unreviewed.yml'])['integration']


@pytest.mark.parametrize('profile', ['daily', 'full'])
@pytest.mark.parametrize('boundary', ['test', 'vet'])
def test_explicit_go_owner_failure_still_stops_source_checks(monkeypatch, profile, boundary):
    import subprocess
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if argv[:2] == ['go', boundary]:
            raise subprocess.CalledProcessError(1, argv)
    monkeypatch.setattr(verify, 'run', run)
    monkeypatch.setattr(verify.subprocess, 'check_output', lambda *a, **kw: '/toolchain\n')
    with pytest.raises(subprocess.CalledProcessError):
        verify.check(profile=profile)
    assert calls[-1][:2] == ['go', boundary]
    assert not any('scripts/check_public.py' in argv for argv in calls)


def test_native_harness_has_only_full_release_check_owner(monkeypatch):
    monkeypatch.setattr(verify.subprocess, 'check_output', lambda *a, **kw: '/toolchain\n')
    for scope_kind, profile, expected in [('full', 'full', True),
                                        ('full', 'daily', False),
                                        ('python', 'daily', False),
                                        ('python', 'full', False)]:
        calls = []
        monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append((argv, kw)))
        verify.check(scope_kind, profile=profile)
        native = [(a, kw) for a, kw in calls if 'tests/native' in a]
        assert bool(native) == expected
        if native:
            assert native[0][1]['env']['MARIAMEM_REQUIRE_PREPARED_C'] == '1'


def test_actual_pytest_collection_excludes_optional_directories_but_allows_explicit_paths(tmp_path):
    import os
    import shutil
    import subprocess
    import sys
    suite = tmp_path/'tests'
    suite.mkdir()
    shutil.copyfile(ROOT/'tests/conftest.py', suite/'conftest.py')
    (suite/'test_daily.py').write_text('def test_daily(): pass\n')
    for name in ('native', 'measurement', 'historical'):
        directory = suite/name
        directory.mkdir()
        (directory/('test_'+name+'.py')).write_text('def test_'+name+'(): pass\n')
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    def collect(*paths):
        result = subprocess.run([sys.executable, '-m', 'pytest', '--collect-only', '-q', *paths],
                                cwd=tmp_path, env=env, text=True, capture_output=True, check=True)
        return [line for line in result.stdout.splitlines() if '::test_' in line]
    daily = collect('tests')
    assert len(daily) == 1 and 'test_daily' in daily[0]
    optional = collect('tests/native', 'tests/measurement')
    assert len(optional) == 2
    assert any('test_native' in line for line in optional)
    assert any('test_measurement' in line for line in optional)


@pytest.mark.parametrize('path', [
    'internal/generatedgo/code/base/memory_mapping.go', 'internal/host/host.go',
    'python/setup.cfg', 'python/mariamem/_artifacts.py', 'scripts/build_alpha.py',
    'scripts/native_target.py', '.github/workflows/linux-wheel.yml',
])
def test_linux_boundaries_select_native_wheel_acceptance(path):
    assert scope.select([path])['linux_wheel']


def test_linux_acceptance_is_not_required_for_plain_docs():
    assert not scope.select(['README.md', 'docs/python.md'])['linux_wheel']


@pytest.mark.parametrize('path', [
    'scripts/update_evidence_records.py', 'release/attribution-tolerance.json',
    'tests/test_update_evidence_records.py',
])
def test_evidence_ledger_tooling_needs_python_checks(path):
    selected = scope.select([path])
    assert selected['check_scope'] == 'python'
    assert not selected['integration']


@pytest.mark.parametrize('path', ['tests/workflow_model.py', 'tests/workflow-requirements.txt',
                                 'tests/routing_acceptance/unit-requirements.txt',
                                 'tests/test_workflow_model.py'])
def test_workflow_test_tooling_has_no_runtime_smoke(path):
    result = scope.select([path])
    assert result['check_scope'] == 'python'
    assert not result['integration'] and not result['linux_wheel']


def test_workflow_migration_keeps_conservative_boundaries():
    assert scope.select(['scripts/development_scope.py'])['linux_wheel']
    for path in ('tests/test_p1_pytest_entry.py', 'tests/test_timer_source.py'):
        result = scope.select([path])
        assert result['check_scope'] == 'full'
        assert result['integration'] and result['linux_wheel']


@pytest.mark.parametrize('path', [
    'tests/test_layout.py', 'tests/test_evidence_retention.py',
    'tests/test_static_image_workflow.py', 'tests/test_canonical_toolchain_pins.py',
])
def test_reviewed_source_only_suites_do_not_build_wheels(path):
    plan = scope.select([path])
    assert plan['check_scope'] == 'python'
    assert not plan['integration'] and not plan['linux_wheel']
    assert scope.select([path, 'scripts/layout.py'])['linux_wheel']
    assert scope.select([path, 'tests/fixtures/new-contract.json'])['integration']


def test_additional_publication_tooling_does_not_select_main_runtime():
    result = scope.select(['scripts/additional_v062.py',
                           'tests/test_additional_v062.py',
                           '.github/workflows/additional-v062-build.yml'])
    assert result['check_scope'] == 'python' and not result['integration']
