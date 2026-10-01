#!/usr/bin/env python3
"""Repeat the isolated actual-pthread ordering reduction on native and Wasmer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--wasmer', type=Path, required=True)
    parser.add_argument('--wasm', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).with_name('pthread-signal-order.c')
    result = {'purpose': 'deterministic pthread ordering, not startup benchmark',
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'wasm_sha256': hashlib.sha256(args.wasm.read_bytes()).hexdigest(),
              'native': [], 'wasmer': []}
    for label, command in [('native', [str(args.native.resolve())]),
                           ('wasmer', [str(args.wasmer.resolve()), 'run',
                                       str(args.wasm.resolve())])]:
        for run in range(args.runs):
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=30, check=True)
            rows = [json.loads(line) for line in completed.stdout.splitlines()]
            assert len(rows) == 2 and all(row['valid'] for row in rows), rows
            assert [row['early_signal'] for row in rows] == [True, False]
            result[label].append({'run': run, 'events': rows})
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
