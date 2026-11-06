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
    'code/base/memfs.go',
    'code/base/block_storage.go',
    'code/base/block_storage_test.go',
    'code/base/heap_snapshot.go',
    'code/base/heap_snapshot_test.go',
    'code/base/fd_allocate_test.go',
    'code/base/bulk_bounds_test.go',
    'code/base/wait_timeout_test.go',
    'code/base/thread_identity_test.go',
    'code/base/thread_lifetime.go',
    'code/base/thread_lifetime_test.go',
    'code/base/runtime_failure.go',
    'code/base/runtime_failure_test.go',
    'runtime_thread_lifetime.go',
    'code/base/narrow_load_test.go',
    'code/base/narrow_load_supported.go',
    'code/base/narrow_load_other.go',
    'code/base/narrow_load_darwin_arm64.s',
    'code/base/narrow_load_linux_amd64.s',
    'code/base/narrow_write_supported.go',
    'code/base/narrow_write_other.go',
    'code/base/narrow_write_darwin_arm64.s',
    'code/base/narrow_write_linux_amd64.s',
    'code/base/narrow_write_test.go',
    'code/base/owned_prepared.go',
    'code/base/owned_prepared_test.go',
    'runtime_instance.go',
    'runtime_instance_test.go',
    'host_dup_test.go',
    'worker_trap_integration_test.go',
    'uca_prepared_integration_test.go',
    'code/base/fd_dup_test.go',
    'code/base/runtime_cleanup.go',
    'code/base/host_memory_test.go',
    'code/base/fd_write_test.go',
    'memory_backing_unix.go',
    'memory_backing_other.go',
    'memory_lifetime.go',
    'memory_backing_test.go',
    'memory_controlled_test.go',
    'memory_host_test.go',
    'code/base/memory_mapping.go',
    'code/base/memory_mapping_test.go',
)


def handwritten_owner(root, name):
    filename = Path(name).name
    if filename.startswith(('narrow_load_', 'narrow_write_')) or filename in {'fd_allocate_test.go','bulk_bounds_test.go','wait_timeout_test.go','thread_identity_test.go'}:
        return root/'scripts/runtime_correctness'/(filename+'.txt')
    return root/'internal/generatedgo'/name


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
        ('func (h *host) Fd_dup(m *base.Module, l0 int32, l1 int32) int32 { panic("unimplemented WASIX: Fd_dup") }',
         '''func (h *host) Fd_dup(m *base.Module, l0 int32, l1 int32) int32 {
 h.flagsMu.Lock()
 defer h.flagsMu.Unlock()
 rc := h.WasiStubs.Fd_dup(m, l0, l1)
 if rc == 0 {
  // dup shares the open file but clears per-descriptor close-on-exec.
  h.fdFlags[int32(binary.LittleEndian.Uint32(m.Memory[l1:]))] = 0
 }
 return rc
}'''),
        ('\tw.SetEnv([]string{"MARIAMEM_GUEST_TIMING=1"})\n\tif !diagnostic {\n\t\tw.SetEnv(nil)\n\t}', '\tw.SetEnv(guestEnvironment(restore != "", diagnostic))'),
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
    parser.add_argument('--development-input', type=Path, help='explicit verified UNQUALIFIED candidate inventory')
    parser.add_argument('--development-thread-binding', type=Path, help='explicit reviewed exact-function binding; UNQUALIFIED route only')
    args = parser.parse_args()
    src = args.source_module.resolve()
    if args.development_input:
        from dev_guest import external_output, install_inputs
        external_output(ROOT, args.output)
        pins = install_inputs(json.loads(args.development_input.read_text()), src, ROOT)
    else:
        pins = json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    files = {str(p.relative_to(src)): hashlib.sha256(p.read_bytes()).hexdigest()
             for suffix in ('*.go', '*.s') for p in src.rglob(suffix)}
    if files != pins['candidate_files_sha256']:
        parser.error('candidate source inventory differs from the pinned input')
    from runtime_thread_lifetime import validate_inputs as thread_lifetime_inputs, apply as thread_lifetime
    development_binding = None
    if args.development_thread_binding:
        if not args.development_input:
            parser.error('experimental thread binding requires UNQUALIFIED development input')
        import re
        from runtime_thread_lifetime import function, apply as canonical_thread_lifetime
        development_binding = json.loads(args.development_thread_binding.read_text())
        if (development_binding['contract'] != 'issue65-experimental-thread-binding-v1' or
                development_binding['guest_sha256'] != pins['guest_sha256'] or
                development_binding['ABI_offsets'] != {'start_args.pthread':16, 'pthread.map_base':40, 'pthread.map_size':44} or
                len(development_binding['functions']) != 3 or
                {v['role'] for v in development_binding['functions'].values()} != {'free','yield','entry'} or
                any(not re.fullmatch(r'code/p\d+/p\d+_pure\.go', k) or
                    not re.fullmatch(r'Fn\d+', v['function']) or
                    not re.fullmatch(r'[0-9a-f]{64}', v['normalized_sha256'])
                    for k, v in development_binding['functions'].items())):
            parser.error('experimental worker binding identity/ABI mismatch')
        def thread_lifetime_inputs(guest_sha, candidate_files):
            required = {'generated/base/base.go', *('generated/'+name.removeprefix('code/') for name in development_binding['functions'])}
            if guest_sha != development_binding['guest_sha256'] or not required <= set(candidate_files):
                raise ValueError('experimental guest/worker binding inputs mismatch')
        def thread_lifetime(name, text):
            if name == 'code/base/base.go':
                return canonical_thread_lifetime(name, text)
            item = development_binding['functions'].get(name)
            if item is None:
                return text
            body = function(text, item['function'])
            if hashlib.sha256(re.sub(r'\s+', '', body).encode()).hexdigest() != item['normalized_sha256']:
                raise ValueError('experimental exact worker function changed: '+item['function'])
            if item['role'] == 'free':
                anchor = 'func '+item['function']+'(m *base.Module, l0 int32) {\n'
                if text.count(anchor) != 1:
                    raise ValueError('experimental free signature mismatch')
                return text.replace(anchor, anchor+'\tif base.DeferThreadAllocationFree(m, l0) { return }\n', 1)
            return text
    thread_lifetime_inputs(pins['guest_sha256'], files)
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
        if name == 'generated/base/base.go':
            from runtime_atomic_loads import apply as narrow_loads
            text = narrow_loads(text)
            from runtime_memfs import apply as memfs
            text = memfs(text)
        if name == 'generated/base/relative.go':
            from runtime_memfs import apply_relative
            text = apply_relative(text)
        if name == 'generated/base/prepared_files.go':
            from runtime_memfs import apply_mapping
            text = apply_mapping(text)
        if name == 'generated/generated.go':
            text = text.replace('\t_ "embed"\n', '')
            text = text.replace('//go:embed data.bin\nvar wasm2goData_data_bin []byte',
                'var wasm2goData_data_bin = []byte("'+''.join('\\x%02x'%b for b in data)+'")')
        elif name == 'main.go':
            text = adapt_driver(text)
        elif name in ('fs_contract_test.go', 'guest_identity.go'):
            text = text.replace('package main', 'package generatedgo', 1)
        text = thread_lifetime(str(target.relative_to(out)), text)
        from runtime_failure import apply as worker_failure
        text = worker_failure(str(target.relative_to(out)), text)
        from runtime_write import apply as write_errors
        text = write_errors(str(target.relative_to(out)), text)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    # Only dedicated mariamem commands dispatch this entry; no consumer init hook.
    (out/'entry.go').write_text('package generatedgo\nconst GuestSHA256 = "'+pins['guest_sha256']+'"\nfunc Run(args []string) { run(args) }\n')
    env=dict(os.environ,GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='')
    go_root=Path(subprocess.check_output(['go','env','GOROOT'],env=env,text=True).strip())
    subprocess.run([str(go_root/'bin/gofmt'),'-w', *map(str,out.rglob('*.go'))], check=True)
    inventory = {str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(out.rglob('*')) if p.is_file()}
    provenance = {'guest_sha256':pins['guest_sha256'],
        'input_manifest_sha256':hashlib.sha256((ROOT/'release/generated-go-inputs.json').read_bytes()).hexdigest(),
        'files_sha256':inventory}
    if args.development_input:
        provenance.update(contract=pins['contract'], result='UNQUALIFIED',
                          dev_inputs_sha256=hashlib.sha256(args.development_input.read_bytes()).hexdigest(),
                          input_manifest_sha256=hashlib.sha256(args.development_input.read_bytes()).hexdigest())
    if development_binding:
        provenance['experimental_thread_binding_sha256'] = hashlib.sha256(args.development_thread_binding.read_bytes()).hexdigest()
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    # Production ownership glue is ordinary handwritten Go, not transpilation
    # output. Carry it into clean regenerated trees without modifying that output.
    for name in HANDWRITTEN_FILES:
        owner = handwritten_owner(ROOT, name)
        shutil.copy2(owner, out/name)
    if development_binding:
        free_file, free_item = next((name, item) for name, item in development_binding['functions'].items() if item['role'] == 'free')
        part = free_file.split('/')[1]
        (out/'runtime_thread_lifetime.go').write_text(
            '// Experimental exact-guest completion binding; not production adoption.\n'
            'package generatedgo\n\nimport (\n'
            '\t"'+NEW+'/base"\n\t"'+NEW+'/'+part+'"\n)\n\n'
            'func installGuestThreadLifetime(m *base.Module) {\n'
            '\tbase.InstallThreadLifetime(m, '+part+'.'+free_item['function']+')\n}\n')
    print('Installed checksum-bound generated runtime:',len(inventory),'files')


if __name__ == '__main__':
    main()
