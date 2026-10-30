"""Regression contracts for compiler reuse and superseded-PR cancellation."""
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ['check', 'live-host', 'dump-import-productization', 'django-lifecycle']


def validate_cancellation(text):
    block = re.search(r'^concurrency:\n(.*?)(?=^\S)', text, re.M | re.S)
    assert block
    # Workflow and event isolate other suites; PR number groups updates, while
    # non-PR runs each get a unique run_id (including pending main/manual runs).
    assert '  group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}\n' in block[1]
    assert "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n" in block[1]


def validate_caches(text, name):
    jobs = re.findall(r'^  ([\w-]+):\n(.*?)(?=^  \S|\Z)', text.split('jobs:\n', 1)[1], re.M | re.S)
    found = 0
    for job, block in jobs:
        if 'uses: actions/setup-go@' not in block:
            continue
        found += 1
        assert 'cache: true' in block and 'cache: false' not in block
        assert 'cache-hit' not in block  # A hit must never skip builds or tests.
        assert 'cache-dependency-path: |\n            go.sum\n            .github/workflows/'+name+'.yml' in block
        assert 'echo "GOCACHE=$(go env GOCACHE)" >> "$GITHUB_ENV"' in block
        assert 'go clean -testcache' in block
        assert block.index('actions/setup-go@') < block.index('go clean -testcache')
        # Invalidating restored PASS must happen before any test/build consumer.
        execution = re.sub(r'          cache-dependency-path: \|\n(?:            [^\n]+\n)+', '', block)
        consumers = [m.start() for m in re.finditer(r'python scripts/verify.py|go test |go build |scripts/build_alpha.py|tests/live_acceptance/installed.py', execution)]
        assert consumers and execution.index('go clean -testcache') < min(consumers)
        # Django cleanup may remove scratch, never the setup-go-managed cache.
        assert 'GOCACHE=$RUNNER_TEMP/' not in block
        if name == 'check' and job == 'check':
            prefix = block.split('shell: bash')[0]
            assert prefix.count("if: needs.scope.outputs.check_scope == 'full'") == 2
    namespaces = re.findall(r'          cache-dependency-path: \|\n((?:            [^\n]+\n)+)', text)
    if name in ('check', 'dump-import-productization', 'live-host'):
        assert len(namespaces) == len(set(namespaces))
    assert found == {'check': 2, 'live-host': 2, 'dump-import-productization': 1, 'django-lifecycle': 1}[name]


@pytest.mark.parametrize('name', WORKFLOWS)
def test_normal_ci_keeps_fresh_tests_and_pr_isolation(name):
    text = (ROOT/'.github/workflows'/f'{name}.yml').read_text()
    if name == 'check':
        validate_cancellation(text)
    validate_caches(text, name)


@pytest.mark.parametrize('before,after', [
    ('github.workflow', 'github.repository'),
    ('github.event.pull_request.number || github.run_id', 'github.ref'),
    ("github.event_name == 'pull_request'", 'true'),
])
def test_cancellation_cannot_include_other_workflows_or_non_pr_runs(before, after):
    text = (ROOT/'.github/workflows/check.yml').read_text()
    with pytest.raises(AssertionError):
        validate_cancellation(text.replace(before, after))


@pytest.mark.parametrize('before,after', [
    ('cache: true', 'cache: false'),
    ('go clean -testcache', 'echo reused-results'),
    ('GOCACHE=$(go env GOCACHE)', 'IGNORED=$(go env GOCACHE)'),
    ('.github/workflows/live-host.yml', 'go.mod'),
])
def test_cache_regressions_are_detected(before, after):
    text = (ROOT/'.github/workflows/live-host.yml').read_text()
    with pytest.raises(AssertionError):
        validate_caches(text.replace(before, after), 'live-host')


def test_cache_export_preserves_paths_with_spaces_and_invalidates_results(tmp_path):
    text = (ROOT/'.github/workflows/live-host.yml').read_text()
    commands = re.search(r'        run: \|\n(          echo "GOCACHE=.*?go clean -testcache\n)', text, re.S)[1]
    commands = '\n'.join(line[10:] for line in commands.splitlines())
    tools = tmp_path/'bin'
    tools.mkdir()
    go = tools/'go'
    go.write_text('#!/bin/sh\nif [ "$1 $2" = "env GOCACHE" ]; then\n  printf "%s\\n" "$CACHE_PATH"\nelif [ "$1 $2" = "clean -testcache" ]; then\n  printf "invalidated\\n" >> "$TEST_LOG"\nelse\n  exit 1\nfi\n')
    go.chmod(0o755)
    output = tmp_path/'github-env'
    log = tmp_path/'test-log'
    cache = str(tmp_path/'compiler cache')
    env = dict(os.environ, PATH=str(tools)+os.pathsep+os.environ['PATH'],
               GITHUB_ENV=str(output), CACHE_PATH=cache, TEST_LOG=str(log))
    subprocess.run(['bash', '-e', '-c', commands], env=env, check=True)
    assert output.read_text() == 'GOCACHE='+cache+'\n'
    assert log.read_text() == 'invalidated\n'
    # build_alpha's existing setdefault must retain the exported compiler path.
    import ast
    tree = ast.parse((ROOT/'scripts/build_alpha.py').read_text())
    statement = next(node for node in tree.body if isinstance(node, ast.Expr)
                     and isinstance(node.value, ast.Call)
                     and ast.unparse(node.value.func) == 'build_env.setdefault')
    inherited = {'GOCACHE': cache}
    exec(compile(ast.Module(body=[statement], type_ignores=[]), 'build_alpha cache', 'exec'),
         {'build_env': inherited, 'ROOT': ROOT})
    assert inherited['GOCACHE'] == cache


def test_pr_does_not_start_macos_acceptance_jobs():
    # Count expanded PR cells from the actual runner and matrix declarations.
    # The selectors may skip more work; this is the selected full-diff ceiling.
    macos = []
    for name in WORKFLOWS:
        text = (ROOT/'.github/workflows'/f'{name}.yml').read_text()
        if '  pull_request:' not in text.split('jobs:')[0]:
            continue
        jobs = re.findall(r'^  ([\w-]+):\n(.*?)(?=^  \S|\Z)', text.split('jobs:\n', 1)[1], re.M | re.S)
        for job, block in jobs:
            runner = re.search(r'^    runs-on: (.+)$', block, re.M)
            assert runner
            if runner[1] == '${{ matrix.os }}':
                if name in ('check', 'django-lifecycle', 'dump-import-productization'):
                    raise AssertionError('daily PR must not launch a platform matrix')
                else:
                    values = re.search(r'^        os: \[([^]]+)\]$', block, re.M)
                    assert values
                    platforms = [v.strip() for v in values[1].split(',')]
            else:
                platforms = [runner[1]]
            python = re.search(r'^        python: \[([^]]+)\]$', block, re.M)
            multiplicity = len(python[1].split(',')) if python else 1
            for platform in platforms:
                if platform.startswith('macos-'):
                    macos.extend([(name, job)] * multiplicity)
    assert macos == []
