#!/usr/bin/env python3
"""Read race logs without running/altering the guest; retain compact signatures.

Signature = unordered pair of (R/W, first generated frame, first guest frame,
actual sync/atomic operation). Absolute addresses, goroutine IDs and deep
recursive stacks do not split a signature. This is an observation census,
not static alias proof. Diagnostics never become production matching rules.
"""
import argparse
import bisect
import collections
import hashlib
import json
from pathlib import Path
import re


def reports(path):
    phase = 'unmarked'
    active = False
    lines = []
    with path.open(errors='replace') as stream:
        for line in stream:
            if 'CENSUS_PHASE ' in line:
                phase = line.strip().split('CENSUS_PHASE ', 1)[1]
            if line.startswith('WARNING: DATA RACE'):
                active, lines = True, []
            elif active and line.startswith('=================='):
                yield phase, lines
                active = False
            elif active:
                lines.append(line)


def endpoints(lines):
    arms, arm, previous = [], None, ''
    for line in lines:
        if re.match(r'^(?:Previous )?(?:Read|Write|read|write) at ', line):
            arm = {'access': 'write' if 'write' in line.lower() else 'read',
                   'atomic': '', 'frames': []}
            arms.append(arm)
        elif line.startswith('Goroutine '):
            arm = None
        elif arm is not None:
            if line.strip().startswith('sync/atomic.'):
                arm['atomic'] = line.strip().split('sync/atomic.', 1)[1].split('(')[0]
            match = re.search(r'/internal/generatedgo/(.*?\.go):(\d+)', line)
            if match:
                arm['frames'].append((previous.strip().split('/')[-1].split('(')[0],
                                      match[1], int(match[2])))
        previous = line
    if len(arms) != 2 or any(not a['frames'] for a in arms):
        return None
    result = []
    for arm in arms:
        first = arm['frames'][0]
        guest = next((f for f in arm['frames'] if re.search(r'/p\d+/', f[1])), first)
        result.append((arm['access'], *first, guest[1], guest[2], arm['atomic']))
    return tuple(sorted(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    counts, sources = collections.Counter(), []
    phase_counts = collections.defaultdict(collections.Counter)
    for path in args.log:
        local, dropped = collections.Counter(), 0
        for phase, lines in reports(path):
            key = endpoints(lines)
            if key is None:
                dropped += 1
                continue
            counts[key] += 1
            local[key] += 1
            phase_counts[key][path.name + ':' + phase] += 1
        digest = hashlib.sha256()
        with path.open('rb') as raw:
            for chunk in iter(lambda: raw.read(1024 * 1024), b''):
                digest.update(chunk)
        sources.append({'file': path.name, 'sha256': digest.hexdigest(),
                        'reports': sum(local.values()), 'signatures': len(local), 'unparsed': dropped})
    files = {}
    for key in counts:
        for e in key:
            path = e[4]
            if path not in files:
                lines = (args.source_root / 'internal/generatedgo' / path).read_text().splitlines()
                starts = [i for i, line in enumerate(lines) if line.startswith('func Fn')]
                files[path] = (lines, starts)
    records = []
    for number, (key, n) in enumerate(sorted(counts.items()), 1):
        ends = []
        for access, function, file, line, guestfile, guestline, atomic in key:
            lines, starts = files[guestfile]
            start = starts[bisect.bisect_right(starts, guestline-1)-1]
            fn = int(re.search(r'Fn(\d+)', lines[start])[1])
            source = lines[guestline-1].strip()
            kind = ('atomic' if atomic or 'Atomic' in function or 'atomic.' in source else
                    'simd' if 'Simd_' in function else
                    'ordinary' if 'unsafe.Add' in source else 'call-frame')
            ends.append({'access': access, 'function': function, 'file': file, 'line': line,
                         'guest_file': guestfile, 'guest_line': guestline, 'wasm_function': fn,
                         'sync_atomic': atomic, 'kind': kind, 'generated': source})
        records.append({'id': number, 'reports': n, 'endpoints': ends,
                        'phases': dict(phase_counts[key])})
    args.output.write_text(json.dumps({'signature_definition': __doc__, 'logs': sources,
                                      'unique_signatures': len(records), 'records': records}, indent=2)+'\n')
    print(json.dumps({'logs': sources, 'unique_signatures': len(records)}, indent=2))


if __name__ == '__main__':
    main()
