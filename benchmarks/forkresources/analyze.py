"""Read-only reproducible analysis of compact per-Fork resource observations."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from statistics import median

STAGES = ['process', 'root_seeded', 'baseline_natural', 'baseline_gc', 'held_1', 'held_1_idle',
          'held_2', 'held_2_idle', 'held_4', 'held_4_idle', 'held_4_gc', 'held_4_mutated',
          'closed_children_natural', 'closed_children_gc', 'closed_children_scavenge',
          'closed_all_natural', 'closed_all_scavenge']


def stats(values):
    return dict(median=round(median(values), 6), minimum=round(min(values), 6), maximum=round(max(values), 6), n=len(values))


def summarize(observations):
    measured = [o for o in observations if not o['record']['warmup'] and not o['record']['negative']]
    assert len(measured) == 10
    assert len(observations) == 12
    out = {'units': 'ms or bytes as named; process CPU can exceed wall; RSS at checkpoints not exclusive memory', 'backends': {}}
    for backend in ['mariamem', 'pgmem']:
        group = [o for o in measured if o['record']['backend'] == backend]
        assert len(group) == 5
        label = 'maria' if backend == 'mariamem' else 'postgres'
        assert {o['record']['name'] for o in group} == {f'matrix/{label}-{i}' for i in range(5)}
        phases = []
        for o in group:
            r = o['result']
            assert r['backend'] == backend and r['success'] and r['cleanup_complete']
            assert o['record']['returncode'] == 0 and o['record']['scratch_empty']
            assert r['gomaxprocs'] == 8 and r['go'] == 'go1.27.3'
            assert [e['stage'] for e in r['events']] == STAGES
            assert [e['stage'] for e in o['rss']] == STAGES
            for s in o['rss']:
                assert s['rss_bytes'] > 0
            pp = [p for e in r['events'] for p in e['phases']]
            assert [p['child'] for p in pp if p['name'] == 'fork'] == [1, 2, 3, 4]
            for p in pp:
                assert p['wall_ms'] >= 0 and p['cpu_ms'] >= 0
                assert abs(p['cpu_ms'] - (p['after']['cpu_ms'] - p['before']['cpu_ms'])) < 0.000001
                assert p['alloc_bytes'] == p['after']['total_alloc_bytes'] - p['before']['total_alloc_bytes']
                assert p['gc_count'] == p['after']['num_gc'] - p['before']['num_gc']
            phases.append(pp)
        result = {'phases': {}, 'stages': {}}
        for phase in ['noop', 'root_start', 'snapshot_and_source_close', 'fork',
                      'connect_select_oracle_retire_connection', 'idle_500ms', 'close_children',
                      'post_close_gc', 'post_close_scavenge', 'held_4_gc']:
            result['phases'][phase] = {}
            for metric in ['wall_ms', 'cpu_ms', 'alloc_bytes', 'mallocs', 'gc_count']:
                # Each process is one independent observation; never treat its children as independent runs.
                values = [median([p[metric] for p in pp if p['name'] == phase]) for pp in phases]
                result['phases'][phase][metric] = stats(values)
        for stage in STAGES:
            fields = {}
            for metric in ['rss_bytes', 'heap_alloc_bytes', 'heap_inuse_bytes', 'go_sys_bytes', 'heap_released_bytes', 'goroutines', 'max_rss_bytes']:
                values = []
                deltas = []
                for o in group:
                    events = {e['stage']: e['metrics'] for e in o['result']['events']}
                    rss = {e['stage']: e['rss_bytes'] for e in o['rss']}
                    v = rss[stage] if metric == 'rss_bytes' else events[stage][metric]
                    baseline = rss['baseline_gc'] if metric == 'rss_bytes' else events['baseline_gc'][metric]
                    values.append(v)
                    deltas.append(v - baseline)
                fields[metric] = stats(values)
                if metric != 'max_rss_bytes':
                    fields[metric + '_delta_from_baseline_gc'] = stats(deltas)
            result['stages'][stage] = fields
        out['backends'][backend] = result
    return out


def json_text(data):
    return json.dumps(data, indent=2) + '\n'


def csv_text(summary):
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(['backend', 'kind', 'name', 'metric', 'median', 'minimum', 'maximum', 'processes'])
    for backend, data in summary['backends'].items():
        for kind, group in data.items():
            for name, fields in group.items():
                for metric, s in fields.items():
                    writer.writerow([backend, kind, name, metric, s['median'], s['minimum'], s['maximum'], s['n']])
    return out.getvalue()


def check(path):
    seals = json.loads((path / 'SHA256SUMS.json').read_text())
    for name, digest in seals.items():
        assert hashlib.sha256((path / name).read_bytes()).hexdigest() == digest, name
    summary = summarize(json.loads((path / 'observations.json').read_text()))
    assert (path / 'summary.json').read_text() == json_text(summary), 'summary JSON mismatch'
    assert (path / 'summary.csv').read_text() == csv_text(summary), 'summary CSV mismatch'
    assert json.loads((path / 'completion.json').read_text())['result'] == 'PASS'
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--results', type=Path, required=True)
    p.add_argument('--collect', type=Path)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    if args.check:
        assert not args.collect
        check(args.results)
        print('PASS: hashes, complete campaign, recomputed JSON/CSV; read-only')
        return
    assert args.collect is not None
    records = json.loads((args.collect / 'matrix-records.json').read_text())
    observations = []
    for row in records:
        observations.append(dict(record=row, result=json.loads((args.collect / row['report']).read_text()), rss=json.loads((args.collect / row['rss']).read_text())))
    summary = summarize(observations)
    args.results.mkdir(parents=True, exist_ok=True)
    (args.results / 'observations.json').write_text(json.dumps(observations, separators=(',', ':')) + '\n')
    (args.results / 'summary.json').write_text(json_text(summary))
    (args.results / 'summary.csv').write_text(csv_text(summary))


if __name__ == '__main__':
    main()
