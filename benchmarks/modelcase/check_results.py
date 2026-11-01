"""Read-only reanalysis of compact model-case results; no runtime or plotting deps."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

PHASES = ('boot', 'schema-master-sample', 'capture-disconnect', 'read-baseline-fork',
          'fork', 'input-oracle', 'read', 'write', 'case-cleanup',
          'read-baseline-cleanup', 'read-baseline-final-oracle')


def extract(raw, shared_read):
    samples = []
    expected = {f'read-{k}-{i:02d}' for k in range(5) for i in range(1, 11)} | {
        f'write-{k}-{i:02d}' for k in range(5) for i in range(1, 5)}
    for record in json.loads((raw / 'records.json').read_text()):
        doc = json.loads((raw / record['report']).read_text())
        if not (doc['completed'] and doc['cleanup_complete'] and
                set(doc['cases']) == expected and all(doc['cases'].values())):
            raise ValueError('raw case completion mismatch')
        if shared_read:
            metrics = dict(suite_ms=doc['suite_ms'],
                           fork_count=sum(s['stage'] in ('fork', 'read-baseline-fork')
                                          for s in doc['spans']),
                           phase_sum_ms={stage: sum(s['duration_ms'] for s in doc['spans']
                                                   if s['stage'] == stage) for stage in PHASES})
        else:
            bodies = [s for s in doc['spans'] if s['stage'] == 'case-body']
            first = min(s['start_ms'] for s in bodies)
            last = max(s['start_ms'] + s['duration_ms'] for s in bodies)
            last = max([last] + [s['start_ms'] + s['duration_ms'] for s in doc['spans']
                                 if s['stage'] == 'case-cleanup'])
            metrics = dict(case_window_ms=last-first, suite_body_ms=doc['suite_ms'])
        samples.append(dict(record=record, metrics=metrics))
    return samples


def summarize(samples, shared_read):
    modes = ['mariamem', 'mariamem-shared-read'] if shared_read else ['mariamem', 'shared', 'workers']
    if len(samples) != len(modes)*4*6:
        raise ValueError('unexpected sample count')
    for sample in samples:
        r = sample['record']
        if (r['mode'] not in modes or r['parallelism'] not in (1, 2, 4, 8) or
                r['returncode'] != 0 or not r['scratch_empty'] or r['cases'] != 70 or
                not math.isfinite(r['wall_ms']) or r['wall_ms'] <= 0):
            raise ValueError('invalid compact execution record')
    rows = []
    for p in (1, 2, 4, 8):
        for mode in modes:
            cell = [s for s in samples if s['record']['parallelism'] == p and s['record']['mode'] == mode]
            measured = [s for s in cell if not s['record']['warmup']]
            if (len(cell) != 6 or len(measured) != 5 or
                    sorted(s['record']['repetition'] for s in measured) != list(range(5)) or
                    [s['record']['repetition'] for s in cell if s['record']['warmup']] != [-1]):
                raise ValueError('missing/duplicate ordinary or warmup sample')
            ordered = sorted(measured, key=lambda s: s['record']['wall_ms'])
            mid = ordered[2]
            r, metrics = mid['record'], mid['metrics']
            timing = dict(parallelism=p, mode=mode, median_ms=r['wall_ms'],
                          min_ms=ordered[0]['record']['wall_ms'], max_ms=ordered[-1]['record']['wall_ms'])
            if shared_read:
                expected_forks = 21 if mode == 'mariamem-shared-read' else 70
                if any(s['metrics']['fork_count'] != expected_forks for s in cell):
                    raise ValueError('Fork count mismatch')
                rows.append(dict(**timing, suite_ms=metrics['suite_ms'], median_run=r['report'],
                                 fork_count=metrics['fork_count'], phase_sum_ms=metrics['phase_sum_ms']))
            else:
                rows.append(dict(case_window_ms=metrics['case_window_ms'], **timing,
                                 median_run=r['report'], suite_body_ms=metrics['suite_body_ms'],
                                 repetitions=5, all_cases_passed=True))
    if shared_read:
        paired = []
        for p in (1, 2, 4, 8):
            by = {m: {s['record']['repetition']: s['record'] for s in samples
                      if not s['record']['warmup'] and s['record']['parallelism'] == p and
                      s['record']['mode'] == m} for m in modes}
            a, b = [next(r['median_ms'] for r in rows if r['parallelism'] == p and r['mode'] == m)
                    for m in modes]
            paired.append(dict(parallelism=p, ratio_of_medians=b/a, reduction_percent=100*(1-b/a),
                               paired_ratio=[by[modes[1]][i]['wall_ms']/by[modes[0]][i]['wall_ms']
                                             for i in range(5)]))
        summary = dict(rows=rows, paired=paired)
    else:
        summary = dict(rows=rows, scope='External process wall; min/max whiskers, not confidence intervals; no performance gate')
    keys = [k for k in rows[0] if k != 'phase_sum_ms']
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=keys, lineterminator='\n')
    writer.writeheader()
    writer.writerows({k: r[k] for k in keys} for r in rows)
    return {'summary.json': json.dumps(summary, indent=2)+'\n', 'summary.csv': output.getvalue()}


def verify_hashes(root):
    for name, expected in json.loads((root / 'SHA256SUMS.json').read_text()).items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'checksum mismatch: {name}')


def same_extraction(a, b):
    # Python3.12 changed float sum accumulation. Raw bytes are hash-pinned;
    # permit only sub-nanosecond-in-ms rounding in derived numeric sums.
    if isinstance(a, float) and isinstance(b, (float, int)):
        return math.isclose(a, b, rel_tol=1e-14, abs_tol=1e-9)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same_extraction(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same_extraction(x, y) for x, y in zip(a, b))
    return a == b


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--raw-root', type=Path, help='also verify the pinned off-main raw extraction')
    args = parser.parse_args()
    try:
        root = args.results
        verify_hashes(root)
        archive = json.loads((root / 'archive.json').read_text())
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != archive['checker_sha256']:
            raise ValueError('checker identity mismatch')
        if json.loads((root / 'completion.json').read_text())['result'] != 'PASS':
            raise ValueError('campaign was not complete')
        shared_read = archive['cohort'] == 'shared-read'
        samples = json.loads((root / 'samples.json').read_text())
        if args.raw_root:
            if hashlib.sha256((args.raw_root / 'SHA256SUMS.json').read_bytes()).hexdigest() != archive['manifest_sha256']:
                raise ValueError('raw archive identity mismatch')
            verify_hashes(args.raw_root)
            if not same_extraction(extract(args.raw_root, shared_read), samples):
                raise ValueError('compact sample extraction mismatch')
        for name, content in summarize(samples, shared_read).items():
            if (root / name).read_bytes() != content.encode():
                raise ValueError(f'recomputed {name} differs')
        print('PASS: compact statistics and hashes; full trace/plot analysis remains in the raw archive')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'FAIL: {exc}\n')


if __name__ == '__main__':
    main()
