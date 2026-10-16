"""Account for the natural pairs and phase/GC observations without dropping data."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import statistics


def cell(path):
    d = json.loads(path.read_text())
    m = d['resources']['after_go']['linear_memory_virtual']
    assert m['creates'] == m['releases'] == 4
    assert m['active_mappings'] == m['active_reserved_bytes'] == m['active_rw_bytes'] == m['release_failures'] == 0
    phases = collections.defaultdict(lambda: {'wall': 0.0, 'cpu': 0.0, 'instances': []})
    for op in d['operations']:
        name = op['name'].rstrip('0123456789_')
        row = phases[name]
        row['wall'] += op['seconds']
        row['cpu'] += op['cpu_seconds']
        row['instances'].append(dict(name=op['name'], wall=op['seconds'], cpu=op['cpu_seconds']))
    o = d['go_resource_observation']
    return dict(source_commit=d['label'], result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        wall=d['suite_product_seconds'], cpu=d['suite_cpu_seconds'], phases=dict(phases),
        allocations_mib=o['cumulative_alloc_bytes'] / 1024**2,
        gc_cycles=o['after']['num_gc'] - o['before']['num_gc'],
        gc_pause_ms=(o['after']['pause_total_ns'] - o['before']['pause_total_ns']) / 1e6,
        mallocs=o['after']['mallocs'] - o['before']['mallocs'])


def paired(a, b):
    return dict(wall_difference_seconds=b['wall'] - a['wall'],
        wall_change_percent=100 * (b['wall'] / a['wall'] - 1),
        cpu_difference_seconds=b['cpu'] - a['cpu'],
        cpu_change_percent=100 * (b['cpu'] / a['cpu'] - 1),
        phase_differences={key: {metric: b['phases'][key][metric] - a['phases'][key][metric]
            for metric in ['wall', 'cpu']} for key in a['phases']})


def profile(path):
    text = path.read_text()
    sample_text, locations_text = text.split('\nLocations\n', 1)
    locations_text = locations_text.split('\nMappings\n', 1)[0]
    locations = {}
    current = None
    for line in locations_text.splitlines():
        match = re.match(r'\s*(\d+): .*?M=\d+ (.*)', line)
        if match:
            current = int(match[1])
            locations[current] = [match[2].split()[0]]
        elif line.strip():
            assert current is not None
            locations[current].append(line.strip().split()[0])
    samples = []
    for line in sample_text.splitlines():
        match = re.fullmatch(r'\s*(\d+)\s+(\d+):\s*([\d ]+)', line)
        if match:
            count, nanos = int(match[1]), int(match[2])
            frames = [frame for loc in map(int, match[3].split()) for frame in locations[loc]]
            samples.append(dict(count=count, nanos=nanos, seconds=nanos / 1e9, frames=frames))
    assert samples and sum(s['count'] for s in samples) * 10000000 == sum(s['nanos'] for s in samples)
    patterns = {
        'storage_union': r'base\.\(\*(?:blockStorage|memFile|MemFS)\)',
        'bounds_union': r'base\.Memory(?:EA|InBounds)$',
        'gc_mark_union': r'^runtime\.(?:gc|scan)',
        'allocation_union': r'^runtime\.(?:mallocgc|makeslice|newobject|growslice)',
        'madvise_union': r'^runtime\.madvise$',
        'heap_reuse_union': r'^runtime\.sysUsed(?:OS)?$',
        'heap_return_union': r'^runtime\.sysUnused(?:OS)?$',
        'cond_signal_flat': r'^runtime\.pthread_cond_signal$',
        'cond_wait_flat': r'^runtime\.pthread_cond_wait$',
        'rawsyscall_flat': r'^syscall\.rawsyscalln$',
    }
    total = sum(s['seconds'] for s in samples)
    groups = {}
    for name, pattern in patterns.items():
        selected = [s for s in samples if any(re.search(pattern, frame) for frame in (s['frames'][:1] if name.endswith('_flat') else s['frames']))]
        seconds = sum(s['seconds'] for s in selected)
        groups[name] = dict(sample_seconds=seconds, percentage=100 * seconds / total)
    return dict(raw_report=path.name, raw_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        sampled_cpu_seconds=total, groups=groups,
        limits='Groups overlap and must not be summed. CPU sample positions, not wall-wait durations. Systemstack allocation samples do not identify the triggering application allocation.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    w = a.workspace.resolve()
    root = Path(__file__).resolve().parents[2]
    old = root / 'benchmarks/main-product-evidence/results'
    historical = []
    for folder, trial in [('matrix', 0), ('large-repeat', 0), ('large-repeat', 1), ('large-repeat', 2)]:
        row = dict(pair=f'{folder}/{trial}')
        for label in ['baseline', 'candidate']:
            source = old / folder / f'{label}-go-large-{trial}-fresh.json'
            row[label] = cell(source)
            row[label]['file'] = source.relative_to(root).as_posix()
        row['difference'] = paired(row['baseline'], row['candidate'])
        historical.append(row)
    out = dict(historical_pairs=historical, definitions={
        'pair': 'Baseline/candidate from the same alternating trial, not arbitrary sorted observations',
        'wall': 'Existing product phase wall excludes diagnostic probe/GC; CPU is process total including diagnostics',
        'off_cpu_limit': 'Wall minus process CPU is not measured wait; multi-thread CPU can exceed elapsed time',
        'gc_pause': 'STW pause counters exclude concurrent/assist GC CPU; cycle counts do not measure time',
        'profiling': 'Full-process samples include workload, Go observer/GC and profile finalization; on/off cohorts stay separate'})
    for metric in ['wall_change_percent', 'cpu_change_percent', 'wall_difference_seconds', 'cpu_difference_seconds']:
        out.setdefault('historical_pair_medians', {})[metric] = statistics.median(r['difference'][metric] for r in historical)
    receipt = json.loads((w / 'evidence/receipt.json').read_text())
    assert receipt['completed'] and len(receipt['cells']) == 10
    current = []
    for row in receipt['cells']:
        assert row['returncode'] == 0
        c = cell(w / 'evidence' / (row['name'] + '.json'))
        assert c['result_sha256'] == row['result_sha256']
        assert c['source_commit'] == receipt['sources'][row['label']]['identity']['source_commit']
        c.update({key: row[key] for key in ['name', 'label', 'kind', 'trial', 'profiled']})
        current.append(c)
    groups = {}
    for kind, profiled in [('calibration', False), ('observer', False), ('observer', True)]:
        key = kind + ('/cpu' if profiled else '/plain')
        group = {}
        for label in ['baseline', 'candidate']:
            cells = [r for r in current if r['kind'] == kind and r['profiled'] == profiled and r['label'] == label]
            assert len(cells) == (1 if kind == 'calibration' else 2)
            group[label] = dict(n=len(cells), wall=[r['wall'] for r in cells], cpu=[r['cpu'] for r in cells],
                median_wall=statistics.median(r['wall'] for r in cells),
                median_cpu=statistics.median(r['cpu'] for r in cells))
        group['median_wall_change_percent'] = 100 * (group['candidate']['median_wall'] / group['baseline']['median_wall'] - 1)
        group['median_cpu_change_percent'] = 100 * (group['candidate']['median_cpu'] / group['baseline']['median_cpu'] - 1)
        group['pairs'] = [paired(next(r for r in current if r['kind'] == kind and r['profiled'] == profiled and r['label'] == 'baseline' and r['trial'] == trial),
            next(r for r in current if r['kind'] == kind and r['profiled'] == profiled and r['label'] == 'candidate' and r['trial'] == trial))
            for trial in range(1 if kind == 'calibration' else 2)]
        groups[key] = group
    out.update(current_cells=current, current_groups=groups, completed_executions=10,
               completed_sql_oracles=True, balanced_memory_mappings=40)
    out['profiles'] = {row['name']: profile(w / 'evidence' / (row['name'] + '-raw.txt'))
        for row in receipt['cells'] if row['profiled']}
    (w / 'evidence/analysis.json').write_text(json.dumps(out, indent=2) + '\n')
    print('Historical paired changes:', out['historical_pair_medians'])
    for key, group in groups.items():
        print(key, 'wall', round(group['baseline']['median_wall'], 3), '->',
              round(group['candidate']['median_wall'], 3), 'change%', round(group['median_wall_change_percent'], 1))
    print('PASS: all observations retained; ten executions and forty DB lifecycles accounted for')


if __name__ == '__main__':
    main()
