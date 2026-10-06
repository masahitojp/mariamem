#!/usr/bin/env python3
"""Sequential, guarded characterization cells. Never run beside other benchmarks."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--helper', type=Path, required=True)
    p.add_argument('--disk-guard', type=Path, required=True)
    p.add_argument('--work-dir', type=Path, required=True)
    p.add_argument('--payloads', nargs='+', type=int, default=[0, 10, 100])
    p.add_argument('--fork-counts', nargs='+', type=int, default=[1, 4, 8, 16])
    p.add_argument('--suite-counts', nargs='+', type=int, default=[1, 4, 8, 16])
    p.add_argument('--mode', choices=['matrix', 'suite', 'both'], default='both')
    p.add_argument('--min-free-gib', type=float, default=12)
    p.add_argument('--budget-gib', type=float, default=4)
    p.add_argument('--max-memory-gib', type=float, default=8)
    p.add_argument('--untraced', action='store_true')
    p.add_argument('--scan-payload', action='store_true')
    p.add_argument('--init-diagnostics', action='store_true')
    p.add_argument('--label', default='')
    a = p.parse_args()
    if any(v < 0 for v in a.payloads) or any(v < 1 for v in a.fork_counts + a.suite_counts):
        p.error('payloads must be nonnegative and counts positive')
    evidence = a.work_dir / 'evidence'
    temp = a.work_dir / 'temp'
    evidence.mkdir(parents=True, exist_ok=True)
    temp.mkdir(parents=True, exist_ok=True)
    cells = []
    for payload in a.payloads:
        if a.mode != 'suite':
            for count in a.fork_counts:
                for mutate in (False, True):
                    cells.append(('matrix', payload, count, mutate))
        if a.mode != 'matrix':
            for count in a.suite_counts:
                cells.append(('suite', payload, count, False))
    receipts = []
    for mode, payload, count, mutate in cells:
        name = f'{mode}-{payload}m-{count}-' + ('mutate' if mutate else 'read')
        if a.untraced:
            name += '-untraced'
        if a.scan_payload:
            name += '-scan'
        if a.init_diagnostics:
            name += '-init'
        if a.label:
            name += '-' + a.label
        output = evidence / (name + '.json')
        if output.exists():
            raise SystemExit(f'refuse overwriting evidence: {output}')
        args = [str(a.binary.resolve()), '--helper', str(a.helper.resolve()), '--out', str(output.resolve()),
                '--mode', mode, '--payload-mib', str(payload),
                '--max-memory-gib', str(a.max_memory_gib), '--trace=' + str(not a.untraced).lower(),
                '--forks' if mode == 'matrix' else '--suite-n', str(count)]
        if mutate:
            args.append('--mutation')
        if a.scan_payload:
            args.append('--scan-payload')
        if a.init_diagnostics:
            args.append('--init-diagnostics')
        # TMPDIR keeps temporary snapshots within the owned disk budget.
        import os
        env = dict(os.environ, TMPDIR=str(temp.resolve()))
        guard = [sys.executable, str(a.disk_guard.resolve()), '--work-dir', str(a.work_dir.resolve()),
                 '--min-free-gib', str(a.min_free_gib), '--budget-gib', str(a.budget_gib),
                 '--timeout', '1800', '--', *args]
        print(name, flush=True)
        with (evidence / (name + '.log')).open('w') as log:
            r = subprocess.run(guard, env=env, stdout=log, stderr=subprocess.STDOUT)
        receipts.append({'cell': name, 'returncode': r.returncode})
        (evidence / ('receipts' + ('-' + a.label if a.label else '') + '.json')).write_text(json.dumps(receipts, indent=2) + '\n')
        if r.returncode:
            raise SystemExit(f'{name} stopped ({r.returncode}); retain partial evidence; inspect log before continuing')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
