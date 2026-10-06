#!/usr/bin/env python3
"""Compact numeric observations; no inference of exclusive/private DB bytes."""
import argparse
import hashlib
import json
import statistics
import re
from pathlib import Path


def ms(values):
    return statistics.median(values) * 1000 if values else None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    cells = []
    for path in sorted(a.evidence.glob('*.json')):
        if not any(label in path.stem for label in ('-full', '-replica', '-scan-scan', '-untraced', '-n2', '-init-diag')):
            continue
        rows = json.loads(path.read_text())
        if not isinstance(rows, list) or not rows or rows[0].get('type') != 'environment':
            continue
        env = rows[0]
        operations = [r for r in rows if r.get('type') == 'operation']
        cp = {r['name']: r for r in rows if r.get('type') == 'checkpoint'}
        inventories = [r for r in rows if r.get('type') == 'inventory']
        stages = {}
        guest_stages = {}
        work = []
        initialization = []
        prepared = False
        for row in rows:
            if row.get("type") == "inventory":
                prepared = True
            if row.get('type') != 'trace':
                continue
            t = row['trace']
            operation = t['operation']
            if operation in ('startup', 'api_startup'):
                operation += '/restore' if prepared else '/fresh'
            events = t['events']
            for before, after in zip(events, events[1:]):
                key = operation + ':' + before['name'] + '→' + after['name']
                stages.setdefault(key, []).append((after['offset_ns'] - before['offset_ns']) / 1e6)
            work.append({'operation': operation, 'bytes_read': sum(e.get('bytes_read', 0) for e in events),
                         'files_touched': sum(e.get('files_touched', 0) for e in events)})
            guest = t.get('guest')
            if isinstance(guest, dict):
                for before, after in zip(guest.get('events', []), guest.get('events', [])[1:]):
                    key = operation + ':' + before['name'] + '→' + after['name']
                    guest_stages.setdefault(key, []).append((after['offset_ns'] - before['offset_ns']) / 1e6)
                if guest.get('initialization'):
                    initialization.append({'operation': t['operation'], 'data':guest['initialization']})
        ready = [r['seconds'] for r in operations if r['name'].startswith('fork_ready_')]
        use = [r['seconds'] for r in operations if r['name'].startswith('fork_use_')]
        cell = {'cell': path.stem, 'environment': env, 'operations': operations, 'checkpoints': cp,
                'inventories': inventories, 'fork_ready_p50_ms': ms(ready), 'fork_ready_max_ms': max(ready) * 1000 if ready else None,
                'fork_use_p50_ms': ms(use), 'stages_p50_ms': {k: statistics.median(v) for k, v in stages.items()},
                 'guest_stages_p50_ms': {k: statistics.median(v) for k, v in guest_stages.items()},
                'verification_work': work, 'initialization': initialization,
                'raw_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        vmmap = path.with_name(path.name + '.vmmap')
        if vmmap.exists():
            match = re.search(r'^mapped file\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', vmmap.read_text(), re.M)
            if match:
                cell['mapped_file_vmmap_rounded'] = dict(zip(['virtual', 'resident', 'dirty', 'swapped'], match.groups()))
        if 'children_live_after_gc' in cp and 'snapshot_retained_after_gc' in cp:
            live, base = cp['children_live_after_gc'], cp['snapshot_retained_after_gc']
            cell['snapshot_to_live_delta'] = {k: live[k] - base[k] for k in ('heap_alloc', 'total_alloc', 'virtual_bytes', 'fds', 'goroutines')}
            cell['snapshot_to_live_delta']['rss_bytes'] = live['os']['rss_bytes'] - base['os']['rss_bytes']
            cell['snapshot_to_live_delta']['physical_bytes'] = live['os']['primary_bytes'] - base['os']['primary_bytes']
        cell['stages_p50_ms'] = {k:v for k,v in cell['stages_p50_ms'].items() if not k.startswith('snapshot_verification:')}
        compact_init = []
        for item in cell['initialization']:
            data = item['data']
            selected = [e for e in data['events'] if e['name'].startswith('innodb_') or e['name'] in ('plugin.InnoDB.begin','plugin.InnoDB.end','guest_main','restore_complete','ready_prepared')]
            compact_init.append({'operation':item['operation'],'events':selected,'dropped_records':data.get('dropped_records'), 'raw_event_count':len(data['events'])})
        cell['initialization'] = compact_init
        aggregate = {}
        for r in cell['verification_work']:
            op = r['operation']
            item = aggregate.setdefault(op, {'traces':0,'bytes_read':0,'files_touched':0})
            item['traces'] += 1
            item['bytes_read'] += r['bytes_read']
            item['files_touched'] += r['files_touched']
        cell['verification_work'] = aggregate
        cells.append(cell)
    a.output.write_text(json.dumps({'cells': cells}, indent=2) + '\n')


if __name__ == '__main__':
    main()
