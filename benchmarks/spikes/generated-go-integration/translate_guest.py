#!/usr/bin/env python3
"""Translate an explicitly checksum-bound guest with the pinned patched generator.

Writes source-only inventory; never silently adopts a guest or enables runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]/'scripts'))
from build_feedback import go_environment, run as observed_run
CONVERTER_SHA = '1adc74bb1594ed1d300d9382b9da27402728939fc021024d977e9c98afd2467f'

PATCHES = ['imported-memory.patch','import-function-index.patch','relaxed-madd.patch','pure-memory32.patch','controlled-thread-traps.patch','host-logical-memory.patch','linear-memory-owner.patch','helper-bridge.patch','export-collision.patch','fd-allocate-preservation.patch','zero-bulk-bounds.patch','wait-timeout-range.patch','thread-id-range.patch']

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest', type=Path, required=True)
    parser.add_argument('--guest-sha256', required=True)
    parser.add_argument('--converter-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be fresh')
    if sha(args.guest) != args.guest_sha256 or sha(args.converter_archive) != CONVERTER_SHA:
        parser.error('input checksum mismatch')
    out = args.output.resolve()
    out.mkdir(parents=True)
    shutil.copyfile(args.guest, out/'guest.wasm')
    (out/'guest.wasm.json').write_text(json.dumps({'wasm_sha256':args.guest_sha256,'module_sha256':args.guest_sha256,'snapshot_version':1})+'\n')
    (out/'go.mod').write_text('module example.com/guest-translation\n\ngo 1.26.0\n')
    converter = out/'converter'
    converter.mkdir()
    with tarfile.open(args.converter_archive) as archive:
        archive.extractall(converter, filter='data')
    source = next(converter.iterdir())
    # Keep patch application inside this extracted source, including in worktrees.
    subprocess.run(['git', 'init', '-q'], cwd=source, check=True)
    env = go_environment(dict(os.environ, GOTOOLCHAIN='go1.26.10', GOWORK='off'))
    patches = HERE.parent/'wasm2go'
    for name in PATCHES:
        subprocess.run(['git','apply','--unidiff-zero',str(patches/name)],cwd=source,check=True)
    binary = out/'wasm2go'
    observed_run(['go','build','-mod=readonly','-trimpath','-buildvcs=false','-o',str(binary),'./cmd/wasm2go'],cwd=source,env=env,check=True,
                 phase='translate:converter-build', inputs=[args.converter_archive], outputs=[binary])
    module = out/'module'
    module.mkdir()
    (module/'go.mod').write_text('module example.com/mariamem-spike\n\ngo 1.26.0\n')
    generated = module/'generated'
    observed_run([str(binary),'-pure','-i',str(args.guest.resolve()),'-out-dir',str(generated),'-pkg','generated','-import','example.com/mariamem-spike/generated'],env=env,check=True,
                 phase='translate:wasm2go', inputs=[args.guest, binary],
                 outputs=[generated/'main.go', generated/'alias.go'])
    (generated/'base/spike_wait.go').write_text('package base\nfunc SpikeWait(m *Module) { if p := m.Threads.WaitThreads(); p != nil { panic(p) } }\n')
    shutil.copyfile(patches/'wait-contract-test.go.txt',generated/'base/spike_contract_test.go')
    inventory = {str(p.relative_to(generated)):sha(p) for p in sorted(generated.rglob('*')) if p.is_file()}
    record = {'guest_sha256':args.guest_sha256,'converter_commit':'730057c146463f663e8774587bc96fb2bea91af8','converter_archive_sha256':CONVERTER_SHA,'patched_converter_sha256':sha(binary),'patches_sha256':{name:sha(patches/name) for name in PATCHES},'files_sha256':inventory}
    (out/'input-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    print(out/'input-manifest.json')


if __name__ == '__main__':
    main()
