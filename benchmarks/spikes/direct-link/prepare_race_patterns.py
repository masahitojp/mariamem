#!/usr/bin/env python3
"""Generate diagnostic WASM/Go in a disposable module, never production code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PIN = 'ac98bcf00c17d8531f0c071a9836d0b50975e7ff'
ARCHIVE_SHA = '1fcd91eecc66e367495d91f34644c68df1ff856a786d00c24fa66061c3dbce0f'


def u(n):
    out = []
    while n >= 128:
        out.append((n & 127) | 128)
        n >>= 7
    return bytes(out + [n])


def vec(items):
    return u(len(items)) + b''.join(items)


def section(kind, data):
    return bytes([kind]) + u(len(data)) + data


def functype(params, results):
    return b'\x60' + vec([bytes([x]) for x in params]) + vec([bytes([x]) for x in results])


def fixture():
    types = [functype([0x7f], [0x7f]), functype([0x7f, 0x7f], []),
             functype([0x7f], []), functype([0x7f], [0x7e]), functype([0x7f, 0x7e], [])]
    # Exact ordinary/atomic/SIMD instructions, not handwritten Go equivalents.
    funcs = [
        ('Read32', 0, b'\x20\x00\x28\x02\x00'),
        ('Store32', 1, b'\x20\x00\x20\x01\x36\x02\x00'),
        ('Inc32', 2, b'\x20\x00\x20\x00\x28\x02\x00\x41\x01\x6a\x36\x02\x00'),
        ('Read8', 0, b'\x20\x00\x2d\x00\x00'),
        ('Store8', 1, b'\x20\x00\x20\x01\x3a\x00\x00'),
        ('AtomicRead8', 0, b'\x20\x00\xfe\x12\x00\x00'),
        ('AtomicStore8', 1, b'\x20\x00\x20\x01\xfe\x19\x00\x00'),
        ('VectorRead', 3, b'\x20\x00\xfd\x00\x04\x00\xfd\x1d\x00'),
        ('VectorStore', 4, b'\x20\x00\x20\x01\xfd\x12\xfd\x0b\x04\x00'),
    ]
    exports = [u(len(name)) + name.encode() + b'\x00' + u(i)
               for i, (name, _, _) in enumerate(funcs)]
    return (b'\0asm\x01\0\0\0' + section(1, vec(types))
            + section(3, vec([u(t) for _, t, _ in funcs]))
            + section(5, b'\x01\x03\x01\x01')  # shared memory: min/max one page
            + section(7, vec(exports))
            + section(10, vec([u(len(code)+2) + b'\0' + code + b'\x0b'
                               for _, _, code in funcs])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--converter', type=Path, required=True)
    parser.add_argument('--converter-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    converter, output = args.converter.resolve(), args.output.resolve()
    archive = args.converter_archive.resolve()
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise SystemExit('converter archive does not match pin')
    critical = ['internal/lower/lower.go', 'internal/codegen/emit_memops.go',
                'internal/codegen/helpers/helpers.go']
    with tarfile.open(archive) as tar:
        for name in critical:
            archived = next(n for n in tar.getnames() if n.endswith('/'+name))
            if tar.extractfile(archived).read() != (converter/name).read_bytes():
                raise SystemExit('converter lowering/helper differs from pinned archive: '+name)
    if output.exists() and any(output.iterdir()):
        raise SystemExit('use a fresh disposable output directory')
    (output/'fixture').mkdir(parents=True)
    (output/'patterns.wasm').write_bytes(fixture())
    (output/'go.mod').write_text('module github.com/masahitojp/mariamem/diagnostics/precheck\n\n'
                               'go 1.26.0\n\nrequire github.com/masahitojp/mariamem v0.0.0\n'
                               f'replace github.com/masahitojp/mariamem => {ROOT}\n')
    for src, dst in [('race-patterns.go.txt', 'patterns_test.go'),
                     ('race-single-db.go.txt', 'census_test.go'),
                     ('futex-precheck-race.go.txt', 'precheck_test.go')]:
        (output/dst).write_bytes((HERE/src).read_bytes())
    env = dict(os.environ, GOTOOLCHAIN='go1.26.8')
    subprocess.run(['go', 'run', './cmd/wasm2go', '-i', str(output/'patterns.wasm'),
                    '-o', str(output/'fixture/fixture.go'), '-pkg', 'fixture',
                    '-import', 'github.com/masahitojp/mariamem/diagnostics/precheck/fixture', '-pure'],
                   cwd=converter, env=env, check=True)
    inventory = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted((output/'fixture').iterdir()) if p.is_file()}
    (output/'manifest.json').write_text(json.dumps({'converter': PIN,
                                                  'converter_archive_sha256': ARCHIVE_SHA,
                                                  'converter_files_sha256': {
                                                      n: hashlib.sha256((converter/n).read_bytes()).hexdigest()
                                                      for n in critical + ['cmd/wasm2go/main.go']},
                                                  'fixture_wasm_sha256': hashlib.sha256(fixture()).hexdigest(),
                                                  'generated_files_sha256': inventory}, indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
