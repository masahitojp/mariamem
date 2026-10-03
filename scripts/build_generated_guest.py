#!/usr/bin/env python3
"""Canonical v0.4 source -> legacy-EH WASM on a fresh Linux arm64 builder.

No Wasmer, AOT, local Docker image, or guest execution is used. Fixed build paths
preserve the accepted recipe; this command intentionally requires an empty /work.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request
from common import ROOT, digest, extract
from install_guest_toolchain import inventory

PIN = ROOT / 'release/generated-go-toolchain.json'


def download(pin, directory):
    path = directory / pin['file']
    directory.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pending = path.with_suffix('.partial')
        try:
            with urllib.request.urlopen(pin['url'], timeout=180) as src, pending.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            if digest(pending) != pin['sha256']:
                raise ValueError('download checksum mismatch: ' + pin['file'])
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)
    if digest(path) != pin['sha256']:
        raise ValueError('cached checksum mismatch: ' + pin['file'])
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=2)
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'aarch64' or os.geteuid() != 0:
        parser.error('requires root on a fresh Linux arm64 build runner (not a product platform)')
    if args.repetitions < 2:
        parser.error('release generation requires at least two independent source builds')
    pins = json.loads(PIN.read_text())
    expected = json.loads((ROOT/'release/generated-go-inputs.json').read_text())['guest_sha256']
    work = Path('/work')
    sdk = Path('/root/.wasixcc')
    if ((work.exists() and any(work.iterdir())) or sdk.exists() or
        any((ROOT/'build'/name).exists() for name in ('source','unpack','generated-release'))):
        parser.error('refuse existing work/SDK/source/output; use a fresh builder')
    archives = {k: download(v, ROOT/'build/downloads') for k,v in pins['archives'].items()}
    work.mkdir(exist_ok=True)
    sdk.mkdir()
    extract(archives['wasixcc'], sdk/'bin')
    # SDK release is flat; the installer creates its named compiler wrappers.
    driver = sdk/'bin/wasixccenv'
    subprocess.run([driver, 'install-executables', sdk/'bin'], check=True)
    extract(archives['sysroot'], sdk/'sysroot-unpack')
    sysroot_payload = sdk/'sysroot-unpack/wasix-sysroot-eh/sysroot'
    if not (sysroot_payload/'lib/wasm32-wasi/libc.a').is_file():
        raise ValueError('unexpected upstream sysroot layout')
    (sdk/'sysroot').mkdir()
    sysroot_payload.rename(sdk/'sysroot/sysroot-eh')
    shutil.rmtree(sdk/'sysroot-unpack')
    extract(archives['binaryen'], sdk/'binaryen-unpack')
    binaryen = next((sdk/'binaryen-unpack').iterdir())
    binaryen.rename(sdk/'binaryen')
    recipe = ROOT/'benchmarks/spikes/generated-go-integration/prepare_llvm23.py'
    # The checksum-verified official LLVM23 and ICU archives are prepared by
    # the same accepted header profile, including the native-only NEON exclusion.
    subprocess.run([sys.executable, recipe, '--llvm-archive', archives['llvm'],
                    '--icu-package', archives['icu'], '--output', sdk/'llvm'], check=True)
    llvm_prefix = next((sdk/'llvm').iterdir())
    llvm_prefix.rename(sdk/'llvm-prepared')
    (sdk/'llvm').rmdir()
    (sdk/'llvm-prepared').rename(sdk/'llvm')
    env = {k:v for k,v in os.environ.items() if not k.startswith('WASIXCC_')}
    env.update(PATH=str(sdk/'bin')+':/usr/bin:/bin', LD_LIBRARY_PATH=str(sdk/'llvm/lib'),
               LC_ALL='C', TZ='UTC', SOURCE_DATE_EPOCH='0')
    toolchain = {'contract': 'generated-go-v1', 'pins_sha256': digest(PIN),
                 'host': 'linux-arm64', 'versions': {}, 'sysroot': inventory(sdk/'sysroot/sysroot-eh'),
                 'archives_sha256': {k:digest(v) for k,v in archives.items()}}
    for key,command in [('wasixcc',[driver,'--version']),('llvm',[sdk/'llvm/bin/clang','--version']),
                         ('lld',[sdk/'llvm/bin/wasm-ld','--version']),('binaryen',[sdk/'binaryen/bin/wasm-opt','--version']),
                         ('cmake',['/usr/bin/cmake','--version']),('bison',['/usr/bin/bison','--version']),
                         ('make',['/usr/bin/make','--version']),('python',[sys.executable,'--version'])]:
        toolchain['versions'][key] = subprocess.check_output(command,env=env,text=True).strip()
    toolchain['environment']={k:env[k] for k in ('PATH','LD_LIBRARY_PATH','LC_ALL','TZ','SOURCE_DATE_EPOCH')}
    results = []
    out = ROOT/'build/generated-release'; out.mkdir()
    shell = ROOT/'benchmarks/spikes/wasm2go/legacy_eh_toolchain.sh'
    for trial in range(args.repetitions):
        subprocess.run([sys.executable, ROOT/'scripts/prepare_guest.py'], env=env, check=True)
        prepared = json.loads((ROOT/'build/prepared-source.json').read_text())
        if prepared.get('experimental_patch'):
            raise ValueError('experimental source patches are forbidden')
        shutil.move(str(ROOT/'build/source'), work/'source')
        subprocess.run(['bash', shell, 'build-no-postopt'], env=env, check=True)
        subprocess.run(['bash', shell, 'postopt'], env=env, check=True)
        linked = work/'artifact/mariamem-legacy-eh.wasm'
        guest = work/'artifact/mariamem-legacy-eh-O2-compatible.wasm'
        result = {'linked_sha256':digest(linked),'guest_sha256':digest(guest)}
        if result['guest_sha256'] != expected:
            raise ValueError('canonical WASM differs; never adopt new guest bytes silently: '+str(result))
        if results and result != results[0]:
            raise ValueError('independent source rebuild differs')
        results.append(result)
        shutil.copy2(guest,out/'mariamem.wasm')
        for name in ('link.txt','flags.make','CMakeCache.txt'):
            shutil.copy2(work/'artifact'/name,out/name)
        shutil.rmtree(work/'source'); shutil.rmtree(ROOT/'build/unpack')
    commit = subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    record = {'contract':'generated-go-v1','source_commit':commit,'guest_sha256':expected,
              'guest_bytes':(out/'mariamem.wasm').stat().st_size,'repetitions':results,
              'prepared_source':prepared,'toolchain':toolchain,
              'canonical_build_sha256':digest(ROOT/'release/generated-go-build.json')}
    (out/'guest.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps(record,indent=2))

if __name__ == '__main__':
    main()
