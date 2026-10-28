#!/usr/bin/env python3
"""Summarize archived PR12 CI JSON/log pairs; never fetch, run or qualify CI.

Inputs: gh run view --json databaseId,headSha,workflowName,event,status,conclusion,
createdAt,startedAt,updatedAt,url,jobs and gh run view --log from the same run.
Dependency maps describe the four workflows at candidate 5304c1b / 5a6bbd1.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

DEPENDENCIES = {
    'Development checks': {'scope': [], 'check': ['scope'], 'integration': ['scope']},
    'Live E2E': {'scope': [], 'native-reference': ['scope'],
                 'live': ['scope', 'native-reference'],
                 'Live required gate': ['scope', 'native-reference', 'live']},
    'Dump reader product candidate': {'scope': [], 'native-reference': [],
                                      'guest-comparison': ['native-reference'],
                                      'development-checks': ['scope'],
                                      'development-integration': ['scope']},
    'Django standard runner recipe': {'native': [], 'recipe': ['native']},
}


def seconds(start, end):
    return round((datetime.fromisoformat(end.replace('Z', '+00:00'))
                  - datetime.fromisoformat(start.replace('Z', '+00:00'))).total_seconds(), 3)


def logical(name):
    return name.split(' (', 1)[0]


def cache_evidence(log):
    """Keep only compact, non-environment cache/identity evidence, never raw logs."""
    observations = {}
    previous = {}
    for line in log.splitlines():
        columns = line.split('\t', 2)
        if len(columns) != 3:
            continue
        name, _, message = columns
        message = re.sub(r'\x1b\[[0-9;]*m', '', message)
        message = re.sub(r'^\ufeff?\d{4}-\d\d-\d\dT[^ ]+ ', '', message)
        item = observations.setdefault(name, {'matches': []})
        if 'git log -1 --format=%H' in previous.get(name, '') and re.fullmatch('[a-f0-9]{40}', message):
            item['checkout_source_commit'] = message
        previous[name] = message
        for prefix, field in [('Cache hit for: ', 'hit_key'),
                              ('Cache restored from key: ', 'restored_key'),
                              ('Cache saved with the key: ', 'saved_key')]:
            if message.startswith(prefix):
                item[field] = message[len(prefix):]
        if message == 'Cache is not found':
            item['miss'] = True
        if message == 'Cache restored successfully':
            item['restored'] = True
        if 'GOCACHE=$(go env GOCACHE)' in message:
            item['exports_go_cache'] = True
        if 'go clean -testcache' in message:
            item['clears_test_results'] = True
        if (message.startswith(('Cache hit for: ', 'Cache restored from key: ',
                                'Cache saved with the key: '))
                or message in ('Cache is not found', 'Cache restored successfully')):
            if message not in item['matches']:
                item['matches'].append(message)
    return observations


def summarize(run, log):
    if run['status'] != 'completed':
        raise ValueError('only completed observations may be summarized')
    graph = DEPENDENCIES[run['workflowName']]
    observations = cache_evidence(log)
    jobs = run['jobs']
    if any(logical(j['name']) not in graph for j in jobs):
        raise ValueError('job is outside the archived dependency profile')
    output = []
    for job in jobs:
        name = job['name']
        parents = graph[logical(name)]
        if any(not any(logical(j['name']) == parent for j in jobs) for parent in parents):
            raise ValueError('dependency metadata missing')
        ready = max([run['createdAt']] + [j['completedAt'] for j in jobs
                                         if logical(j['name']) in parents])
        skipped = job['conclusion'] == 'skipped'
        row = dict(name=name, conclusion=job['conclusion'], started_at=job['startedAt'],
                   completed_at=job['completedAt'], dependency_ready_at=ready,
                   job_wall_seconds=0 if skipped else seconds(job['startedAt'], job['completedAt']),
                   ready_to_start_seconds=None if skipped else max(0, seconds(ready, job['startedAt'])),
                   cache=observations.get(name, {}), steps=[])
        for step in job['steps']:
            if any(token in step['name'] for token in [
                    'Share Go compiler', 'verify.py', 'Canonical ', 'Exact clean source',
                    'Standard runner', 'Installed wheel', 'Pinned interpreter consumers']):
                row['steps'].append(dict(name=step['name'], conclusion=step['conclusion'],
                                         seconds=seconds(step['startedAt'], step['completedAt'])))
        output.append(row)
    return dict(run_id=run['databaseId'], url=run['url'], workflow=run['workflowName'],
                event=run['event'], head_commit=run['headSha'], conclusion=run['conclusion'],
                created_at=run['createdAt'],
                completed_at=max(j['completedAt'] for j in jobs),
                workflow_wall_seconds=seconds(run['createdAt'], max(j['completedAt'] for j in jobs)),
                summed_job_wall_seconds=round(sum(j['job_wall_seconds'] for j in output), 3), jobs=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', nargs=2, action='append', required=True, metavar=('JSON', 'LOG'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = dict(schema='mariamem-ci-efficiency-observations-v1',
                  dependency_profile='pr12-four-workflows-5304c1b-5a6bbd1',
                  limits=[
                      'Observed PR executions, not a controlled cache-only benchmark.',
                      'Head commit is distinct from the checkout source commit in each job log.',
                      'Job wall sums are unweighted occupied-job proxies, not billed minutes.',
                      'Ready-to-start includes scheduler/provisioning delay after dependencies; not a pure queue metric.',
                      'Workflow wall times overlap; never add them as PR elapsed time.',
                      'Timing summaries do not replace source-bound test or qualification receipts.',
                  ], runs=[])
    for metadata, log in args.run:
        json_path, log_path = Path(metadata), Path(log)
        item = summarize(json.loads(json_path.read_text()), log_path.read_text())
        item['input_sha256'] = {'run_json': hashlib.sha256(json_path.read_bytes()).hexdigest(),
                                'run_log': hashlib.sha256(log_path.read_bytes()).hexdigest()}
        result['runs'].append(item)
    result['cohorts'] = []
    for head in sorted({r['head_commit'] for r in result['runs']}):
        cohort = [r for r in result['runs'] if r['head_commit'] == head]
        if len(cohort) != len(DEPENDENCIES) or {r['workflow'] for r in cohort} != set(DEPENDENCIES):
            raise ValueError('a cohort must include each of the four workflows once')
        result['cohorts'].append(dict(head_commit=head, run_ids=[r['run_id'] for r in cohort],
                                      all_workflows_conclusion_success=all(r['conclusion'] == 'success' for r in cohort),
                                      pr_wall_seconds=seconds(min(r['created_at'] for r in cohort), max(r['completed_at'] for r in cohort)),
                                      summed_job_wall_seconds=round(sum(r['summed_job_wall_seconds'] for r in cohort), 3),
                                      max_ready_to_start_seconds=max(j['ready_to_start_seconds'] or 0 for r in cohort for j in r['jobs'])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['cohorts'], indent=2))


if __name__ == '__main__':
    main()
