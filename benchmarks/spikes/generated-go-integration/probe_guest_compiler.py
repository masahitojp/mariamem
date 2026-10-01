#!/usr/bin/env python3
"""Repeat the implicated translation unit with identical flags and pass dumps.

Requires an existing isolated guest-build work directory. Does not overwrite
build objects or alter the toolchain. Output must be fresh.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

IMAGE = 'sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f'
FUNCTION = '_Z15log_write_up_toybPK19completion_callback'
MARKER = '# *** IR Dump After WebAssembly CFG Stackify (wasm-cfg-stackify) ***:'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--name', default='compiler-repro')
    parser.add_argument('--trials', type=int, default=10)
    parser.add_argument('--llvm-dir', type=Path, help='isolated compiler override; original driver/sysroot remain unchanged')
    args = parser.parse_args()
    if args.trials < 2:
        parser.error('at least two trials required')
    if not args.name or Path(args.name).name != args.name or args.name in ('.', '..'):
        parser.error('name must be a single directory component')
    work = args.work.resolve()
    out = work / args.name
    if out.exists():
        parser.error('output must be fresh')
    flags = work / 'source/build-legacy-no-postopt/storage/innobase/CMakeFiles/innobase_embedded.dir/flags.make'
    values = {}
    for line in flags.read_text().splitlines():
        if ' = ' in line and not line.startswith('#'):
            key, value = line.split(' = ', 1)
            values[key] = value
    command = ['/root/.wasixcc/bin/wasixcc++']
    for key in ['CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS']:
        command.extend(shlex.split(values[key]))
    unit = '/work/source/storage/innobase/log/log0log.cc'
    out.mkdir()
    lines = ['#!/bin/bash', 'set -euo pipefail', 'export WASIXCC_WASM_EXCEPTIONS=legacy WASIXCC_RUN_WASM_OPT=no', 'cd /work/source/build-legacy-no-postopt/storage/innobase']
    lines.append(shlex.join(command + ['-E', unit, '-o', f'/work/{args.name}/input.ii']))
    for i in range(args.trials):
        prefix = f'/work/{args.name}/run-{i+1}'
        argv = command + ['-mllvm', '-print-before=wasm-cfg-stackify', '-mllvm', '-print-after=wasm-cfg-stackify', '-mllvm', f'-filter-print-funcs={FUNCTION}', '-c', unit, '-o', prefix + '.o']
        lines.append(shlex.join(argv) + ' 2>' + shlex.quote(prefix + '.log'))
    driver = out / 'driver.sh'
    driver.write_text('\n'.join(lines) + '\n')
    docker = ['docker', 'run', '--rm', '--network', 'none', '--platform', 'linux/arm64', '--mount', f'type=bind,src={work},dst=/work']
    if args.llvm_dir:
        docker += ['--mount', f'type=bind,src={args.llvm_dir.resolve()},dst=/root/.wasixcc/llvm,readonly', '--env', 'LD_LIBRARY_PATH=/root/.wasixcc/llvm/lib']
    subprocess.run(docker + [IMAGE, 'bash', f'/work/{args.name}/driver.sh'], check=True)
    records = []
    for i in range(args.trials):
        prefix = out / f'run-{i+1}'
        parts = prefix.with_suffix('.log').read_text().split(MARKER)
        if len(parts) != 2:
            raise RuntimeError('compiler pass dump missing')
        records.append({'run': i+1, 'object_sha256': sha(prefix.with_suffix('.o')), 'before_sha256': hashlib.sha256(parts[0].encode()).hexdigest(), 'after_sha256': hashlib.sha256(parts[1].encode()).hexdigest()})
    result = {'image': IMAGE, 'flags_sha256': sha(flags), 'preprocessed_sha256': sha(out/'input.ii'), 'function': FUNCTION, 'trials': records, 'before_variants': len({x['before_sha256'] for x in records}), 'after_variants': len({x['after_sha256'] for x in records})}
    (out/'evidence.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
