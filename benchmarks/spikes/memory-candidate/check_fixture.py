#!/usr/bin/env python3
"""Deterministic pure memory32 regressions against pinned WASM-reference results.

Requires the pinned patched converter binary and Go 1.26.8. Output must be a new
owned directory. Node/Wasmer are unnecessary for regression replay; use
reference.js separately when reviewing fixture changes, never auto-update goldens.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from fixtures import build

HERE = Path(__file__).resolve().parent
KEYS = ['op', 'addr', 'grow', 'trap', 'value', 'before', 'after']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--converter', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    fixture = args.output/'inputs'
    count = build(fixture)
    golden = json.loads((HERE/'reference-results.json').read_text())
    digest = hashlib.sha256((fixture/'contract.wasm').read_bytes()).hexdigest()
    if digest != golden['fixture_sha256'] or count != len(golden['rows']):
        parser.error('fixture identity changed; review against a WASM reference')
    project = args.output/'module'
    (project/'fixture').mkdir(parents=True)
    (project/'go.mod').write_text('module genericfixture\n\ngo 1.26.0\n')
    shutil.copyfile(HERE/'matrix.go.txt', project/'main.go')
    subprocess.run([str(args.converter.resolve()), '-pure', '-i', str((fixture/'contract.wasm').resolve()), '-o', str((project/'fixture/fixture.go').resolve()), '-pkg', 'fixture', '-import', 'genericfixture/fixture'], check=True)
    env = dict(os.environ, GOTOOLCHAIN='go1.26.8', GOWORK='off', GOENV='off', GOFLAGS='', GOEXPERIMENT='')
    result = subprocess.run(['go', 'run', '.', str((fixture/'matrix.json').resolve())], cwd=project, env=env, capture_output=True, text=True, check=True)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    actual = [[row[key] for key in KEYS] for row in rows]
    if actual != golden['rows']:
        raise ValueError('valid values, traps or memory effects differ from WASM reference')
    print(result.stderr.strip())
    print('PASS:', count, 'cases;', sum(row['trap'] for row in rows), 'guest traps; host exit 0')

if __name__ == '__main__':
    main()
