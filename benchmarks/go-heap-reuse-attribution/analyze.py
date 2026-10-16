"""Replay all four observations; allocation samples are estimates, not syscall attribution."""
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import re


def reuse_stacks(path):
    samples, locations = path.read_text().split('\nLocations\n', 1)
    locs = {}
    current = None
    for line in locations.split('\nMappings\n', 1)[0].splitlines():
        m = re.match(r'\s*(\d+): .*?M=\d+ (.*)', line)
        if m:
            current = int(m[1])
            locs[current] = [m[2].split()[0]]
        elif line.strip():
            assert current is not None
            locs[current].append(line.strip().split()[0])
    rows = []
    for line in samples.splitlines():
        m = re.fullmatch(r'\s*(\d+)\s+(\d+):\s*([\d ]+)', line)
        if m:
            frames = [f for i in map(int, m[3].split()) for f in locs[i]]
            if any(f in ['runtime.sysUsed', 'runtime.sysUsedOS'] for f in frames):
                rows.append(dict(nanoseconds=int(m[2]), frames=frames))
    return rows


def allocs(path):
    text = path.read_text()
    samples, locations = text.split('\nLocations\n', 1)
    locations = locations.split('\nMappings\n', 1)[0]
    locs = {}
    current = None
    for line in locations.splitlines():
        m = re.match(r'\s*(\d+): .*?M=\d+ (.*)', line)
        if m:
            current = int(m[1])
            locs[current] = [m[2].split()[0]]
        elif line.strip():
            assert current is not None
            locs[current].append(line.strip().split()[0])
    rows = []
    for line in samples.splitlines():
        size = re.fullmatch(r'\s*bytes:\[([\d ]+)\]\s*', line)
        if size:
            assert rows
            rows[-1]['sample_allocation_size_bytes'] = list(map(int, size[1].split()))
            continue
        m = re.fullmatch(r'\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+):\s*([\d ]+)', line)
        if not m:
            continue
        values = [int(m[i]) for i in range(1, 5)]
        frames = [f for i in map(int, m[5].split()) for f in locs[i]]
        joined = '\n'.join(frames)
        # Exclusive categories, first match wins. Expose every stack below too.
        if 'base.(*blockStorage)' in joined:
            kind = 'D_block_storage'
        elif 'base.(*memFile)' in joined or 'base.(*MemFS)' in joined:
            kind = 'other_MemFS'
        elif 'go-sql-driver/mysql' in joined or 'internal/mysqlwire' in joined:
            kind = 'SQL_transport'
        elif 'main.main' in joined:
            kind = 'other_workload_descendant'
        else:
            kind = 'other_runtime_or_background'
        rows.append(dict(alloc_objects=values[0], alloc_bytes=values[1], inuse_objects=values[2], inuse_bytes=values[3], category=kind, frames=frames))
    assert rows, 'No allocation samples parsed'
    totals = collections.defaultdict(lambda: dict(alloc_bytes=0, alloc_objects=0, inuse_bytes=0))
    for row in rows:
        for key in ['alloc_bytes', 'alloc_objects', 'inuse_bytes']:
            totals[row['category']][key] += row[key]
    return dict(estimated_totals={key: sum(r[key] for r in rows) for key in ['alloc_bytes', 'alloc_objects', 'inuse_bytes']}, categories=dict(totals), stacks=sorted(rows, key=lambda r: r['alloc_bytes'], reverse=True), limits='Default MemProfileRate sampling and completed-GC visibility; estimated bytes, not exact allocation accounting. Categories exclusive in priority order. No assignment of sysUsed CPU to callers.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    evidence = a.workspace / 'evidence'
    spec = importlib.util.spec_from_file_location('previous', Path(__file__).parents[1] / 'go-large-fresh/analyze.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    receipt = json.loads((evidence / 'receipt.json').read_text())
    assert receipt['completed'] and len(receipt['cells']) == 4
    output = dict(cells=[], limits='All are instrumented runs; no new uninstrumented calibration or causal counterfactual. Per-phase resource probes are outside phase timers but may perturb subsequent GC/scavenging.')
    for row in receipt['cells']:
        path = evidence / (row['name'] + '.json')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['result_sha256']
        c = old.cell(path)
        assert c['source_commit'] == receipt['sources'][row['label']]['identity']['source_commit']
        c.update(name=row['name'], label=row['label'], trial=row['trial'])
        d = json.loads(path.read_text())
        c['per_phase'] = []
        for op in d['operations']:
            before, after = op['heap_before'], op['heap_after']
            bounds = before['allocation_size_bounds']
            assert bounds == after['allocation_size_bounds']
            counts = [b-a for a,b in zip(before['allocation_size_counts'], after['allocation_size_counts'])]
            assert len(bounds) == len(counts)+1 and all(x >= 0 for x in counts)
            hist = [dict(lower=bounds[i], upper_exclusive=bounds[i+1], count=v) for i,v in enumerate(counts) if v]
            c['per_phase'].append(dict(name=op['name'], wall=op['seconds'], cpu=op['cpu_seconds'], before=before, after=after, allocation_size_count_deltas=hist, delta={k: after[k]-before[k] for k in ['total_alloc_bytes','mallocs','num_gc','pause_total_ns','heap_alloc_bytes','heap_inuse_bytes','heap_sys_bytes','heap_released_bytes']}))
        c['cpu_profile'] = old.profile(evidence / (row['name'] + '-raw.txt'))
        c['heap_reuse_stacks'] = reuse_stacks(evidence / (row['name'] + '-raw.txt'))
        assert abs(sum(r['nanoseconds'] for r in c['heap_reuse_stacks']) / 1e9 - c['cpu_profile']['groups']['heap_reuse_union']['sample_seconds']) < 1e-8
        c['allocation_profile'] = allocs(evidence / (row['name'] + '-allocs-raw.txt'))
        output['cells'].append(c)
        print(row['name'], 'wall', round(c['wall'],3), 'CPU', round(c['cpu'],3), 'alloc MiB',round(c['allocations_mib'],1), 'sysUsed',round(c['cpu_profile']['groups']['heap_reuse_union']['sample_seconds'],2), 'categories', {k: round(v['alloc_bytes']/2**20,1) for k,v in c['allocation_profile']['categories'].items()})
    output['pairs'] = [old.paired(next(c for c in output['cells'] if c['trial']==i and c['label']=='baseline'), next(c for c in output['cells'] if c['trial']==i and c['label']=='candidate')) for i in range(2)]
    (evidence/'analysis.json').write_text(json.dumps(output,indent=2)+'\n')
    print('PASS: four result hashes, SQL/cleanup receipts, all allocation sample stacks and every phase retained')


if __name__ == '__main__':
    main()
