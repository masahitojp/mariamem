#!/usr/bin/env python3
"""Isolated UNQUALIFIED upstream feasibility; never writes canonical artifacts.

This is an experiment adapter around the existing translation/source installer,
not a replacement build/release entry point. All input hashes are fixed below.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from build_feedback import go_environment, run
from git_identity import require_commit

UPSTREAM = '730057c146463f663e8774587bc96fb2bea91af8'
ARCHIVE = '1adc74bb1594ed1d300d9382b9da27402728939fc021024d977e9c98afd2467f'
GUEST = '33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008'
SERIES = ['imported-memory.patch', 'import-function-index.patch', 'relaxed-madd.patch',
          'upstream-pure-memory32.patch', 'controlled-thread-traps.patch',
          'host-logical-memory.patch', 'linear-memory-owner.patch',
          'upstream-helper-bridge.patch', 'upstream-export-collision.patch']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def inventory(path):
    return {p.relative_to(path).as_posix(): sha(p)
            for p in sorted(path.rglob('*')) if p.is_file()}


def write(path, record):
    path.write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--guest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    require_commit(ROOT, commit)
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip():
        parser.error('commit experiment source before execution')
    if sha(args.archive) != ARCHIVE or sha(args.guest) != GUEST:
        parser.error('fixed input hash mismatch')
    out = args.output.resolve()
    if out.exists() or out.is_relative_to(ROOT) or ROOT.is_relative_to(out):
        parser.error('fresh output outside the source checkout required')
    out.mkdir(parents=True)
    env = go_environment(dict(os.environ, GOTOOLCHAIN='go1.26.8', GOWORK='off',
                              GOENV='off', GOFLAGS='', GOEXPERIMENT=''))
    patches = ROOT/'benchmarks/spikes/wasm2go'
    observed = {'contract':'experiment-upstream-unqualified-v1','result':'UNQUALIFIED',
                'source_commit':commit, 'converter_source_commit':UPSTREAM,
                'converter_archive_sha256':ARCHIVE, 'guest_sha256':GUEST,
                'series':SERIES,'patches_sha256':{n:sha(patches/n) for n in SERIES}}
    write(out/'inputs.json', observed)
    try:
        source = out/'converter'
        source.mkdir()
        with tarfile.open(args.archive) as archive:
            archive.extractall(source, filter='data')
        source = next(source.iterdir())
        # A local Git boundary avoids inherited outer-worktree path prefixes.
        run(['git','init','-q'],cwd=source,check=True,phase='upstream:source-boundary')
        for name in SERIES:
            run(['git','apply','--check','--unidiff-zero',str(patches/name)],cwd=source,
                check=True,phase='upstream:patch-check:'+name)
            run(['git','apply','--unidiff-zero',str(patches/name)],cwd=source,
                check=True,phase='upstream:patch:'+name)
        observed['patched_source_inventory'] = {
            p.relative_to(source).as_posix():sha(p) for p in sorted(source.rglob('*'))
            if p.is_file() and '.git' not in p.relative_to(source).parts}
        binary = out/'wasm2go'
        run(['go','build','-mod=readonly','-trimpath','-buildvcs=false','-o',str(binary),
             './cmd/wasm2go'],cwd=source,env=env,check=True,
            phase='upstream:converter-build',inputs=[args.archive,out/'inputs.json'],outputs=[binary])
        observed['patched_converter_sha256'] = sha(binary)
        # Retain patch-owned emitter/SSA regressions, not unrelated gcasm tests.
        run(['go','test','-p','1','./internal/codegen','./internal/ssa','./internal/ssa/pass',
             '-run','Test(PureMemory32RetainsIndividualStores|MemoryAccessWidths|TrappingLoadIsObservable|DCEKeepsTrappingLoad|ExportMethodNameCollisionPreservation)$',
             '-count=1'],
            cwd=source,env=env,check=True,phase='upstream:converter-regressions')
        run([sys.executable,str(ROOT/'benchmarks/spikes/memory-candidate/check_fixture.py'),
             '--converter',str(binary),'--output',str(out/'memory32')],
            env=env,check=True,phase='upstream:memory32-reference')
        module = out/'translation/module'
        module.mkdir(parents=True)
        (module/'go.mod').write_text('module example.com/mariamem-spike\n\ngo 1.26.0\n')
        generated = module/'generated'
        run([str(binary),'-pure','-i',str(args.guest.resolve()),'-out-dir',str(generated),
             '-pkg','generated','-import','example.com/mariamem-spike/generated'],
            env=env,check=True,phase='upstream:guest-translation',inputs=[args.guest,binary],
            outputs=[generated/'main.go',generated/'alias.go'])
        (generated/'base/spike_wait.go').write_text(
            'package base\nfunc SpikeWait(m *Module) { if p := m.Threads.WaitThreads(); p != nil { panic(p) } }\n')
        shutil.copyfile(patches/'wait-contract-test.go.txt',generated/'base/spike_contract_test.go')
        observed['files_sha256'] = inventory(generated)
        manifest = out/'translation/input-manifest.json'
        write(manifest, observed)
        run([sys.executable,str(ROOT/'benchmarks/spikes/generated-go-integration/setup_candidate.py'),
             '--source-only','--source-module',str(module),'--guest',str(args.guest.resolve()),
             '--input-manifest',str(manifest),'--output',str(out/'candidate')],
            env=env,check=True,phase='upstream:source-adapter')
        candidate = out/'candidate/module'
        pins = {'guest_sha256':GUEST,'data_sha256':sha(candidate/'generated/data.bin'),
                'candidate_files_sha256':{p.relative_to(candidate).as_posix():sha(p)
                 for suffix in ('*.go','*.s') for p in candidate.rglob(suffix)},
                'contract':observed['contract'],'result':'UNQUALIFIED'}
        inputs = out/'installation-inputs.json'
        write(inputs,pins)
        # Reuse the exact installer transformations and canonical handwritten
        # overlays. Replace only input acquisition in an external script copy;
        # canonical pins, validators and source remain unchanged.
        installer = (ROOT/'scripts/generate_runtime.py').read_text()
        replacements = [
            ('ROOT = Path(__file__).resolve().parents[1]', 'ROOT = Path('+repr(str(ROOT))+')'),
            ("pins = json.loads((ROOT/'release/generated-go-inputs.json').read_text())",
             'pins = json.loads(Path('+repr(str(inputs))+').read_text())'),
            ("hashlib.sha256((ROOT/'release/generated-go-inputs.json').read_bytes()).hexdigest()",
             'hashlib.sha256(Path('+repr(str(inputs))+').read_bytes()).hexdigest()')]
        for old,new in replacements:
            if installer.count(old) != 1:
                raise ValueError('installer input boundary changed: '+old)
            installer = installer.replace(old,new,1)
        adapter = out/'install-experiment.py'
        adapter.write_text(installer)
        product = out/'product'
        names = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
        for name in names:
            if not name or name.startswith('internal/generatedgo/'):
                continue
            dest = product/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,dest)
        runtime = product/'internal/generatedgo'
        run([sys.executable,str(adapter),'--source-module',str(candidate),'--output',str(runtime)],
            env=env,check=True,phase='upstream:runtime-install')
        provenance = json.loads((runtime/'provenance.json').read_text())
        provenance.update(contract=observed['contract'],result='UNQUALIFIED',
                          experiment_inputs_sha256=sha(out/'inputs.json'))
        write(runtime/'provenance.json',provenance)
        host = out/'mariamem-experiment-host'
        run(['go','build','-p','1','-trimpath','-buildvcs=false','-o',str(host),'./cmd/mariamem-host'],
            cwd=product,env=env,check=True,phase='upstream:generated-go-compilation',
            inputs=[manifest,inputs,runtime/'provenance.json'],outputs=[host])
        observed.update(binary_sha256=sha(host),binary_bytes=host.stat().st_size,
                        installed_inventory=inventory(runtime),
                        toolchain=subprocess.check_output(['go','version'],env=env,text=True).strip())
        write(out/'candidate.json',observed)
        print('UNQUALIFIED candidate built; run focused real runtime checks separately:',product)
    except BaseException as exc:
        write(out/'failure.json',{'result':'FAILED','exception':type(exc).__name__,'message':str(exc)})
        raise


if __name__ == '__main__':
    main()
