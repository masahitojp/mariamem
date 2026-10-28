"""Offline CI observations must separate occupied time from dependency/dispatch delay."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import summarize_ci_efficiency as summary


def timestamp(second):
    return f'2026-10-28T10:00:{second:02d}Z'


def job(name, start, end, conclusion='success'):
    return dict(name=name, startedAt=timestamp(start), completedAt=timestamp(end),
                conclusion=conclusion, steps=[])


def run(jobs):
    return dict(workflowName='Django standard runner recipe', status='completed',
                createdAt=timestamp(0), databaseId=123, url='https://example.invalid/run/123',
                event='pull_request', headSha='a'*40, conclusion='success', jobs=jobs)


def test_parallel_wall_sum_and_dependency_ready_delay_are_distinct():
    observed = summary.summarize(run([
        job('native (3.11)', 0, 20), job('native (3.14)', 5, 30),
        job('recipe (ubuntu-24.04, 3.11)', 40, 50),
    ]), '')
    assert observed['workflow_wall_seconds'] == 50
    assert observed['summed_job_wall_seconds'] == 55
    recipe = observed['jobs'][-1]
    assert recipe['dependency_ready_at'] == timestamp(30)
    assert recipe['ready_to_start_seconds'] == 10  # Not forty seconds of queueing.
    assert recipe['job_wall_seconds'] == 10
    assert 'checkout_source_commit' not in recipe['cache']


def test_skipped_job_does_not_consume_runner_seconds():
    data = run([job('native (3.11)', 0, 20), job('native (3.14)', 0, 30),
                job('recipe (ubuntu-24.04, 3.11)', 0, 40, 'skipped')])
    observed = summary.summarize(data, '')
    assert observed['summed_job_wall_seconds'] == 50
    assert observed['jobs'][-1]['ready_to_start_seconds'] is None


def test_cache_proof_keeps_checkout_commit_separate_from_head_and_environment():
    sha = 'b'*40
    messages = ['[command]/usr/bin/git log -1 --format=%H', sha,
                'Cache hit for: key-A', 'Cache restored successfully',
                'Cache restored from key: key-A', 'Cache saved with the key: key-B',
                'Cache is not found', 'echo "GOCACHE=$(go env GOCACHE)"',
                'go clean -testcache', 'GITHUB_TOKEN: must-not-retain',
                'local environment value: must-not-retain']
    log = '\n'.join('native (3.11)\tUNKNOWN STEP\t'+timestamp(0)+' '+m for m in messages)
    observed = summary.summarize(run([job('native (3.11)', 0, 20)]), log)
    assert observed['head_commit'] == 'a'*40
    cache = observed['jobs'][0]['cache']
    assert cache['checkout_source_commit'] == sha
    assert cache['hit_key'] == cache['restored_key'] == 'key-A'
    assert cache['saved_key'] == 'key-B' and cache['miss'] and cache['restored']
    assert cache['exports_go_cache'] and cache['clears_test_results']
    assert 'must-not-retain' not in repr(observed)


@pytest.mark.parametrize('kind', ['running', 'unknown-job', 'missing-dependency'])
def test_incomplete_or_unmodelled_inputs_are_rejected(kind):
    data = run([job('native (3.11)', 0, 20)])
    if kind == 'running':
        data['status'] = 'in_progress'
    if kind == 'unknown-job':
        data['jobs'].append(job('mystery', 20, 30))
    if kind == 'missing-dependency':
        data['jobs'] = [job('recipe (ubuntu-24.04, 3.11)', 20, 30)]
    with pytest.raises(ValueError):
        summary.summarize(data, '')
