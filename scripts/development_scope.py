#!/usr/bin/env python3
"""Select local development checks from the event diff, never release receipts.

Unknown inputs conservatively require check + integration. This selector produces
an execution plan, not reusable runtime or final-artifact qualification evidence.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess

from git_identity import require_commit

ROOT = Path(__file__).resolve().parents[1]
# Explicit tooling boundaries; do not classify every .py file as runtime-free.
TOOLING = {
    # Archived measurement recipes; reproduction explicitly checks out its
    # pinned source and does not execute these in runtime/release qualification.
    'docs/benchmarks/go126-vs-go127-evidence/build.py',
    'docs/benchmarks/go126-vs-go127-evidence/profile.py',
    'docs/benchmarks/go126-vs-go127-evidence/summarize.py',
    'tests/verify_alpha.py', 'tests/consumer/run_gorm.py', 'tests/consumer/run_sqlalchemy.py',
    'scripts/generated_release_acceptance.py', 'scripts/release_generated_ci.py',
    'scripts/validate_product_candidate.py', 'scripts/guest_smoke/main.go',
    '.github/workflows/v044-product-validation.yml',
    'benchmarks/ownedprepared/test_tools.py',
    'scripts/published_assets.py', 'benchmarks/measurement_summary.py',
    'benchmarks/v04_candidate.py',
    'scripts/development_scope.py', 'scripts/check_public.py', 'scripts/check_version.py',
    'scripts/git_identity.py', 'scripts/experiment_workspace.py', 'scripts/experiment_disk.py',
    'scripts/release_prepare.py', 'scripts/release_version.py', 'scripts/release_plan.py',
    'scripts/release_preparation_checks.py', 'scripts/runtime_validation.py',
    'scripts/ci_release_reuse.py', 'scripts/ci_release_publish.py',
    'scripts/ci_release_summary.py', 'scripts/check_release.py',
    'scripts/distribution_licenses.py', 'scripts/audit_generated_licenses.py',
    'scripts/consumer_module.py', 'scripts/consumer_acceptance.py',
    '.github/workflows/check.yml', '.github/workflows/release-candidate-ready.yml',
    'AGENTS.md', '.agents/skills/release/SKILL.md',
    '.agents/skills/experiment-workspace/SKILL.md',
}
# Only already-owned non-real-host suites are runtime-free. New test files are
# unknown until deliberately assigned a responsibility, even if named .py.
PURE_TESTS = {
    'tests/test_measurement_summary.py', 'tests/test_published_assets.py',
    'tests/test_benchmark_inputs.py',
    'tests/test_ci_publication_workflow.py',
    'tests/test_ci_release_publish.py',
    'tests/test_ci_release_reuse.py',
    'tests/test_competitive_benchmark.py',
    'tests/test_consumer_acceptance.py',
    'tests/test_deployment.py',
    'tests/test_development_cleanup.py',
    'tests/test_development_scope.py',
    'tests/test_distribution_licenses.py',
    'tests/test_experiment_workspace.py',
    'tests/test_final_latency.py',
    'tests/test_generated_default.py',
    'tests/test_generated_release.py',
    'tests/test_generated_runtime_inventory.py',
    'tests/test_git_identity.py',
    'tests/test_go_isolation.py',
    'tests/test_guest_auth_hooks.py',
    'tests/test_guest_provenance.py',
    'tests/test_guest_repro_tools.py',
    'tests/test_guest_startup_timing.py',
    'tests/test_init_diagnostics.py',
    'tests/test_isolation_baseline.py',
    'tests/test_memory_envelope.py',
    'tests/test_native_target.py',
    'tests/test_owned_snapshot_unit.py',
    'tests/test_packaging_license_mirrors.py',
    'tests/test_practical_suites.py',
    'tests/test_prepared_auth_keys.py',
    'tests/test_python_diagnostics.py',
    'tests/test_release_docs.py',
    'tests/test_release_plan.py',
    'tests/test_release_prepare.py',
    'tests/test_release_tools.py',
    'tests/test_release_version.py',
    'tests/test_runtime_sources.py',
    'tests/test_runtime_validation.py',
    'tests/test_snapshot_copy.py',
    'tests/test_v04_direct_link_report.py',
    'tests/test_v04_verification_scope.py',
    'tests/test_verification_report.py',
    'tests/test_vet_generated.py',
}


def boundary(path):
    p = Path(path)
    if p.is_absolute() or '..' in p.parts:
        return 'runtime'
    # Reviewed, inert measurement data only. Other docs inputs/extensions still
    # fail closed; this is not a blanket exemption for documentation directories.
    if any(path.startswith(prefix) for prefix in (
            'docs/benchmarks/go126-vs-go127-evidence/',
            'docs/reviews/memfs-discovery-evidence/')) and (
            p.suffix in ('.json', '.csv', '.txt') or p.name == 'SHA256SUMS'):
        return 'docs'
    if path in ('README.md', 'CONTRIBUTING.md',
                'benchmarks/README.md',
                'docs/reviews/v044-runtime-validation-intent.json',
                'docs/reviews/v045-p1-evidence.json') or (path.startswith('docs/') and p.suffix == '.md'):
        return 'docs'
    if path in TOOLING:
        return 'python'
    if path in PURE_TESTS:
        return 'python'
    return 'runtime'


def select(paths, *, fallback=None):
    scopes = {boundary(path) for path in paths}
    full = bool(fallback or not paths or 'runtime' in scopes)
    return {'version': 1, 'check_scope': 'full' if full else ('python' if 'python' in scopes else 'docs'),
            'integration': full, 'changed_paths': sorted(set(paths)),
            'reason': fallback or ('unknown/runtime input' if full else 'local changed-input classification')}


def event_base(event, name):
    if name == 'pull_request':
        return event.get('pull_request', {}).get('base', {}).get('sha')
    if name == 'push':
        return event.get('before')
    return None


def plan(root, candidate, base):
    # Candidate identity is never silently downgraded. No tag-object inputs.
    require_commit(root, candidate)
    if not base or base == '0' * 40:
        result = select([], fallback='event base unavailable; full verification')
    else:
        try:
            require_commit(root, base)
            proc = subprocess.run(['git', 'diff', '--name-only', '--no-renames', '-z', base, candidate, '--'],
                                  cwd=root, check=True, capture_output=True)
            paths = proc.stdout.decode('utf-8').split('\0')[:-1]
            result = select(paths)
        except (ValueError, subprocess.CalledProcessError, UnicodeError):
            result = select([], fallback='event diff unavailable; full verification')
    return {**result, 'source_commit': candidate, 'base_commit': base}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--candidate-sha', required=True)
    parser.add_argument('--base-sha')
    parser.add_argument('--github-output', action='store_true')
    args = parser.parse_args()
    base = args.base_sha
    if base is None and os.environ.get('GITHUB_EVENT_PATH'):
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        base = event_base(event, os.environ.get('GITHUB_EVENT_NAME'))
    result = plan(args.root, args.candidate_sha, base)
    print(json.dumps(result, indent=2))
    if args.github_output:
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
            output.write('check_scope=' + result['check_scope'] + '\n')
            output.write('integration=' + str(result['integration']).lower() + '\n')


if __name__ == '__main__':
    main()
