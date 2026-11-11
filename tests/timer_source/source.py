"""Apply only canonical timer hunks to checksum-pinned upstream fixtures."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def prepare_inputs(work):
    pins = json.loads((HERE / 'inputs.json').read_text())
    source = work / 'source'
    source.mkdir(parents=True)
    originals = {}
    for name, digest in pins['upstream_files'].items():
        data = (HERE / 'upstream' / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('timer fixture drift: ' + name)
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        originals[name] = data.decode()
    patch = (ROOT / 'guest/source.patch').read_text()
    blocks = re.split(r'(?m)(?=^--- a/)', patch)
    selected = []
    for name in ('sql/sql_analyze_stmt.h', 'mysys/my_rdtsc.c'):
        matches = [b for b in blocks if b.startswith('--- a/' + name + '\n')]
        if len(matches) != 1:
            raise ValueError('canonical timer patch missing/duplicated: ' + name)
        selected.append(matches[0])
    if '--- a/include/my_rdtsc.h\n' in patch:
        raise ValueError('global clock header changed; review source-unit scope')
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1'],
                   input=''.join(selected), text=True, cwd=source,
                   check=True, capture_output=True)
    return pins, source, originals
