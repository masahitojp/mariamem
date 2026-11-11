"""Recompute the compact diagnostic summary; --check never writes evidence."""
import argparse
import collections
import csv
import json
import math
from pathlib import Path
import statistics


def summarize(root):
    with (root / 'observations.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 220
    groups = collections.defaultdict(list)
    phases = ['setup', 'pages', 'contractions', 'hash_allocate',
              'hash_zero', 'hash_populate', 'remaining']
    for row in rows:
        groups[(row['run'], row['instance'])].append(row)
        assert sum(int(row[p + '_ns']) for p in phases) <= int(row['total_ns'])
        for phase in phases:
            assert int(row[phase + '_count']) == (1 if phase == 'setup' else 3)
    assert len(groups) == 44
    totals = {'fresh': [], 'fork': []}
    for children in groups.values():
        assert {int(r['id']) for r in children} == {2048, 2304, 2560, 2816, 3072}
        assert len(children) == 5
        assert len({r['restored'] for r in children}) == 1
        kind = 'fork' if children[0]['restored'] == '1' else 'fresh'
        total = {p: sum(int(r[p + '_ns']) for r in children) for p in phases}
        total['total'] = sum(int(r['total_ns']) for r in children)
        totals[kind].append(total)
    assert len(totals['fork']) == 42 and len(totals['fresh']) == 2
    result = {'unit': 'elapsed milliseconds, diagnostic observer enabled',
              'p95_method': 'nearest rank', 'groups': {}}
    for kind, samples in totals.items():
        denominator = sum(x['total'] for x in samples)
        stats = {}
        for phase in phases + ['total']:
            values = sorted(x[phase] / 1e6 for x in samples)
            stats[phase] = {
                'p50_ms': statistics.median(values),
                'p95_ms': values[math.ceil(.95 * len(values)) - 1],
                'aggregate_share_percent': 100 * sum(x[phase] for x in samples) / denominator,
            }
        result['groups'][kind] = {'n': len(samples), 'phases': stats}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    result = summarize(root)
    path = root / 'summary.json'
    if args.check:
        assert result == json.loads(path.read_text()), 'summary mismatch'
        print('compact UCA summary PASS (read-only)')
    else:
        path.write_text(json.dumps(result, indent=2) + '\n')
