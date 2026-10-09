#!/usr/bin/env python3
"""Install checksum-bound candidate source as the built-in generated-Go guest.

First reproduce the legacy-EH guest and candidate using the documented scripts.
This deterministic import/package/data transformation needs no manual patches.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OLD = 'example.com/mariamem-spike/generated'
NEW = 'github.com/masahitojp/mariamem/internal/generatedgo/code'
# Canonical installer ownership boundary; the verifier consumes this same list.
HANDWRITTEN_FILES = (
    'code/base/owned_prepared.go',
    'code/base/owned_prepared_test.go',
    'runtime_instance.go',
    'runtime_instance_test.go',
    'code/base/runtime_cleanup.go',
    'code/base/host_memory_test.go',
    'memory_backing_unix.go',
    'memory_backing_other.go',
    'memory_lifetime.go',
    'memory_backing_test.go',
    'memory_controlled_test.go',
    'memory_host_test.go',
    'code/base/memory_mapping.go',
    'code/base/memory_mapping_test.go',
)


def adapt_driver(text):
    text = text.replace('package main', 'package generatedgo', 1)
    text = text.replace('\t"crypto/sha256"\n', '').replace('\t"io"\n', '')
    text = text.replace('func main() {', 'func run(args []string) {', 1).replace('os.Args', 'args')
    begin = text.index('func verifyCompiledGuest(name string) {')
    text = text[:begin]+'''func verifyCompiledGuest(name string) {
 if name != GuestSHA256 { panic("compiled guest identity mismatch") }
}
'''
    text = text.replace('SPIKE', 'generated-Go')
    text = text.replace('m := generated.NewWithWASI(h, nil, h)', 'm, release, allocErr := newMemoryModule(h)\n\tif allocErr != nil { panic(allocErr) }\n\tvar memoryErr error\n\tdefer func(){ releaseMemoryModule(m, release, &memoryErr); if memoryErr != nil { panic(memoryErr) } }()')
    # Export attribution belongs to this deterministic adapter, not a manual
    # edit of its generated output. Reject an unexpected pinned driver shape.
    changes = (
        ('import (\n', 'import (\n\t"context"\n'),
        ('\t"os"\n', '\t"os"\n\t"github.com/masahitojp/mariamem/internal/timing"\n'),
        ('\tvar walk func(string, string) error\n', '\tctx, finishTiming := timing.Begin(context.Background(), "snapshot_export")\n\tdefer finishTiming()\n\tvar walk func(string, string) error\n'),
        ('\t\tb := make([]byte, st.Size())\n', '\t\ttiming.Mark(ctx, "allocation_begin")\n\t\tb := make([]byte, st.Size())\n\t\ttiming.Mark(ctx, "allocation_done")\n'),
        ('\t\t_, e = f.ReadAt(b, 0)\n', '\t\t_, e = f.ReadAt(b, 0)\n\t\ttiming.Work(ctx, "data_read", int64(len(b)), 1)\n'),
        ('\t\treturn os.WriteFile(dst, b, 0600)\n', '\t\te = os.WriteFile(dst, b, 0600)\n\t\ttiming.Work(ctx, "data_materialized", int64(len(b)), 1)\n\t\treturn e\n'),
    )
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError('pinned export driver fragment changed: ' + repr(old))
        text = text.replace(old, new, 1)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-module', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'internal/generatedgo')
    args = parser.parse_args()
    pins = json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    src = args.source_module.resolve()
    files = {str(p.relative_to(src)): hashlib.sha256(p.read_bytes()).hexdigest()
             for suffix in ('*.go', '*.s') for p in src.rglob(suffix)}
    if files != pins['candidate_files_sha256']:
        parser.error('candidate source inventory differs from the pinned input')
    data = (src/'generated/data.bin').read_bytes()
    if hashlib.sha256(data).hexdigest() != pins['data_sha256']:
        parser.error('initial guest data identity mismatch')
    out = args.output.resolve()
    if out.exists():
        parser.error('output must be fresh')
    (out/'code').mkdir(parents=True)
    for name in files:
        source = src/name
        # The driver regression belongs alongside the handwritten host adapter.
        target = out/('code/'+name[len('generated/'):] if name.startswith('generated/') else name)
        text = source.read_text().replace(OLD, NEW)
        if name == 'generated/generated.go':
            text = text.replace('\t_ "embed"\n', '')
            text = text.replace('//go:embed data.bin\nvar wasm2goData_data_bin []byte',
                'var wasm2goData_data_bin = []byte("'+''.join('\\x%02x'%b for b in data)+'")')
        elif name == 'main.go':
            text = adapt_driver(text)
        elif name in ('fs_contract_test.go', 'guest_identity.go'):
            text = text.replace('package main', 'package generatedgo', 1)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    # Only dedicated mariamem commands dispatch this entry; no consumer init hook.
    (out/'entry.go').write_text('package generatedgo\nconst GuestSHA256 = "'+pins['guest_sha256']+'"\nfunc Run(args []string) { run(args) }\n')
    env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='')
    go_root=Path(subprocess.check_output(['go','env','GOROOT'],env=env,text=True).strip())
    subprocess.run([str(go_root/'bin/gofmt'),'-w', *map(str,out.rglob('*.go'))], check=True)
    inventory = {str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'provenance.json').write_text(json.dumps({'guest_sha256':pins['guest_sha256'],
        'input_manifest_sha256':hashlib.sha256((ROOT/'release/generated-go-inputs.json').read_bytes()).hexdigest(),
        'files_sha256':inventory},indent=2)+'\n')
    # Production ownership glue is ordinary handwritten Go, not transpilation
    # output. Carry it into clean regenerated trees without modifying that output.
    for name in HANDWRITTEN_FILES:
        shutil.copy2(ROOT/'internal/generatedgo'/name, out/name)
    print('Installed checksum-bound generated runtime:',len(inventory),'files')


if __name__ == '__main__':
    main()
