#!/usr/bin/env python3
"""Canonical v0.4 source -> legacy-EH WASM on a fresh Linux arm64 builder.

No Wasmer, AOT, local Docker image, or guest execution is used. Fixed build paths
preserve the accepted recipe; this command intentionally requires an empty /work.
"""
from layout import BENCHMARKS
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
import urllib.request
from common import ROOT, digest, extract
from build_feedback import run as observed_run

PIN = ROOT / 'release/generated-go-toolchain.json'
# Alternate transport for the same pinned Ubuntu archive.
ICU_PORTS_URL = 'https://ports.ubuntu.com/ubuntu-ports/pool/main/i/icu/libicu70_70.1-2_arm64.deb'
ICU_LAUNCHPAD_URL = 'https://launchpad.net/ubuntu/+archive/primary/+files/libicu70_70.1-2_arm64.deb'
USER_AGENT = 'mariamem-guest-builder/1.0'


def inventory(root):
    entries = {}
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries[name] = ['symlink', os.readlink(path)]
        elif path.is_file():
            entries[name] = ['file', digest(path)]
    encoded = json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()
    return {'entries': len(entries), 'inventory_sha256': hashlib.sha256(encoded).hexdigest()}


def download(pin, directory):
    path = directory / pin['file']
    directory.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pending = path.with_suffix('.partial')
        primary = pin['url']
        urls = (primary, ICU_LAUNCHPAD_URL) if primary == ICU_PORTS_URL else (primary,)
        for url in urls:
            origin = urlsplit(url).hostname
            print(f'Downloading {path.name} from {origin}', file=sys.stderr, flush=True)
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            try:
                with urllib.request.urlopen(request, timeout=180) as src, pending.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
                if digest(pending) != pin['sha256']:
                    raise ValueError('download checksum mismatch: ' + pin['file'])
                pending.replace(path)
                break
            except HTTPError as error:
                responder = urlsplit(error.geturl()).hostname or origin
                message = f'Could not download {path.name} from {origin} (HTTP {error.code} from {responder})'
                if url == ICU_PORTS_URL and error.code in (403, 404, 408, 429, 500, 502, 503, 504):
                    print(message + '; trying the Ubuntu archive on Launchpad', file=sys.stderr, flush=True)
                    continue
                raise RuntimeError(message) from error
            finally:
                pending.unlink(missing_ok=True)
    if digest(path) != pin['sha256']:
        raise ValueError('cached checksum mismatch: ' + pin['file'])
    return path


def build_binaryen(pins, archive, sdk):
    backport = pins['binaryen_backport']
    patch = ROOT / backport['patch']
    if digest(patch) != backport['patch_sha256']:
        raise ValueError('Binaryen backport patch checksum differs')
    source_root = sdk/'binaryen-source'
    extract(archive, source_root)
    source = source_root/('binaryen-' + backport['source_commit'])
    output = sdk/'binaryen'
    env = dict(os.environ, PATH='/usr/bin:/bin', LC_ALL='C', TZ='UTC', SOURCE_DATE_EPOCH='0')
    inputs = [PIN, patch, archive]
    observed_run(['/usr/bin/patch', '--fuzz=0', '-p1', '--batch', '--forward', '-i', patch],
                 cwd=source, env=env, check=True, phase='guest:binaryen-patch', inputs=inputs)
    observed_run(['/usr/bin/cmake', '-S', source, '-B', output, '-G', 'Ninja',
                  '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_C_COMPILER=/usr/bin/gcc',
                  '-DCMAKE_CXX_COMPILER=/usr/bin/g++', '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG',
                  '-DCMAKE_C_FLAGS_RELEASE=-O2 -DNDEBUG', '-DBUILD_TESTS=OFF', '-DBUILD_LLVM_DWARF=ON'],
                 env=env, check=True, phase='guest:binaryen-configure', inputs=inputs)
    optimizer = output/'bin/wasm-opt'
    library = output/'lib/libbinaryen.so'
    observed_run(['/usr/bin/cmake', '--build', output, '--target', 'wasm-opt', '--parallel', '6'],
                 env=env, check=True, phase='guest:binaryen-build', inputs=inputs,
                 outputs=[optimizer, library])
    fixture = source/'test/lit/passes/precompute_all-features.wast'
    result = output/'atomic-fence-regression.wat'
    observed_run([optimizer, fixture, '--all-features', '--precompute', '-S', '-g', '-o', result],
                 env=env, check=True, phase='guest:binaryen-atomic-fence', inputs=[optimizer, library, fixture],
                 outputs=[result])
    if not re.search(r'^ \(func \$atomic-fence \(type [^)]+\)\n'
                     r'  \(atomic\.fence\)\n  \(atomic\.fence acqrel\)\n \)$',
                     result.read_text(), re.MULTILINE):
        raise ValueError('Binaryen precompute removed an atomic fence')
    return dict(backport, optimizer_sha256=digest(optimizer), library_sha256=digest(library),
                compiler=subprocess.check_output(['/usr/bin/g++', '--version'], env=env, text=True).splitlines()[0],
                atomic_fence='PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--development-output', type=Path, help='explicit external UNQUALIFIED single-build output; never release evidence')
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'aarch64' or os.geteuid() != 0:
        parser.error('requires root on a fresh Linux arm64 build runner (not a product platform)')
    development = args.development_output is not None
    if development and args.repetitions != 2:
        parser.error('development route has exactly one build; do not specify --repetitions')
    if args.repetitions < 2:
        parser.error('release generation requires at least two independent source builds')
    if development:
        from dev_guest import external_output, source_identity, CONTRACT
        out = external_output(ROOT, args.development_output)
        identity = source_identity(ROOT)
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
    observed_run([driver, 'install-executables', sdk/'bin'], check=True,
                 phase='guest:sdk-install', inputs=[PIN])
    (sdk/'sysroot').mkdir()
    for archive_key, variant in [('sysroot', 'sysroot-eh'), ('sysroot_pic', 'sysroot-ehpic')]:
        unpack = sdk/(variant+'-unpack')
        extract(archives[archive_key], unpack)
        payload = unpack/('wasix-'+variant)/'sysroot'
        if not (payload/'lib/wasm32-wasi/libc.a').is_file():
            raise ValueError('unexpected upstream sysroot layout: '+variant)
        payload.rename(sdk/'sysroot'/variant)
        shutil.rmtree(unpack)
    binaryen = build_binaryen(pins, archives['binaryen'], sdk)
    recipe = ROOT/(BENCHMARKS / 'spikes/generated-go-integration/prepare_llvm23.py')
    # The checksum-verified official LLVM23 and ICU archives are prepared by
    # the same accepted header profile, including the native-only NEON exclusion.
    observed_run([sys.executable, recipe, '--llvm-archive', archives['llvm'],
                  '--icu-package', archives['icu'], '--output', sdk/'llvm'], check=True,
                 phase='guest:llvm-prepare', inputs=[PIN, recipe])
    llvm_prefix = next((sdk/'llvm').iterdir())
    llvm_prefix.rename(sdk/'llvm-prepared')
    (sdk/'llvm').rmdir()
    (sdk/'llvm-prepared').rename(sdk/'llvm')
    env = {k:v for k,v in os.environ.items() if not k.startswith('WASIXCC_')}
    env.update(PATH=str(sdk/'bin')+':/usr/bin:/bin', LD_LIBRARY_PATH=str(sdk/'llvm/lib'),
               LC_ALL='C', TZ='UTC', SOURCE_DATE_EPOCH='0')
    toolchain = {'contract': 'generated-go-v1', 'pins_sha256': digest(PIN),
                 'host': 'linux-arm64', 'versions': {}, 'sysroot': inventory(sdk/'sysroot'),
                 'archives_sha256': {k:digest(v) for k,v in archives.items()}}
    toolchain['binaryen_backport'] = binaryen
    for key,command in [('wasixcc',[driver,'--version']),('llvm',[sdk/'llvm/bin/clang','--version']),
                         ('lld',[sdk/'llvm/bin/wasm-ld','--version']),('binaryen',[sdk/'binaryen/bin/wasm-opt','--version']),
                         ('cmake',['/usr/bin/cmake','--version']),('bison',['/usr/bin/bison','--version']),
                         ('make',['/usr/bin/make','--version']),('python',[sys.executable,'--version'])]:
        toolchain['versions'][key] = subprocess.check_output(command,env=env,text=True).strip()
    toolchain['environment']={k:env[k] for k in ('PATH','LD_LIBRARY_PATH','LC_ALL','TZ','SOURCE_DATE_EPOCH')}
    results = []
    if not development:
        out = ROOT/'build/generated-release'
    out.mkdir(parents=True)
    shell = ROOT/(BENCHMARKS / 'spikes/wasm2go/legacy_eh_toolchain.sh')
    for trial in range(1 if development else args.repetitions):
        observed_run([sys.executable, ROOT/'scripts/prepare_guest.py'], env=env, check=True,
                     phase=f'guest:prepare:{trial}', inputs=[ROOT/'release/inputs.lock.json',
                     ROOT/'guest/source.patch'], outputs=[ROOT/'build/prepared-source.json'],
                     tools=toolchain['versions'])
        prepared = json.loads((ROOT/'build/prepared-source.json').read_text())
        if not development and prepared.get('experimental_patch'):
            raise ValueError('experimental source patches are forbidden')
        if not development:
            observed_run([sys.executable, ROOT/'scripts/check_dictionary_wait_source.py',
                          '--prepared-source', ROOT/'build/source'],
                         env=env, check=True, phase=f'guest:dictionary-wait-source:{trial}',
                         inputs=[ROOT/'guest/source.patch'])
            observed_run([sys.executable, ROOT/'scripts/check_history_wait_source.py'],
                         env=env, check=True, phase=f'guest:history-wait-source:{trial}',
                         inputs=[ROOT/'guest/source.patch'])
            observed_run([sys.executable, ROOT/'tests/history_wait_contract.py',
                          ROOT/'build/source', ROOT/'build'/f'history-wait-contract-{trial}'],
                         env=env, check=True, phase=f'guest:history-wait-contract:{trial}',
                         inputs=[ROOT/'guest/source.patch', ROOT/'tests/history_wait_contract.py'])
        # Exercise the actual prepared C allocator contract before compilation.
        allocator_check = ROOT/'build'/f'buffer-pool-contract-{trial}.json'
        observed_run([sys.executable, ROOT/'tests/buffer_pool_alignment_check.py',
                      '--source', ROOT/'build/source', '--output', allocator_check],
                     env=env, check=True, phase=f'guest:allocator-contract:{trial}',
                     inputs=[ROOT/'guest/input.json', ROOT/'tests/buffer_pool_alignment_check.py'],
                     outputs=[allocator_check])
        shutil.move(str(ROOT/'build/source'), work/'source')
        linked = work/'artifact/mariamem-legacy-eh.wasm'
        guest = work/'artifact/mariamem-legacy-eh-O2-compatible.wasm'
        observed_run(['bash', shell, 'build-no-postopt'], env=env, check=True,
                     phase=f'guest:compile-link:{trial}', inputs=[PIN, shell, ROOT/'build/prepared-source.json'],
                     outputs=[linked], tools=toolchain['versions'])
        observed_run(['bash', shell, 'postopt'], env=env, check=True,
                     phase=f'guest:wasm-postopt:{trial}', inputs=[linked, shell, sdk/'binaryen/bin/wasm-opt',
                     sdk/'binaryen/lib/libbinaryen.so'],
                     outputs=[guest], tools=toolchain['versions'])
        result = {'linked_sha256':digest(linked),'guest_sha256':digest(guest)}
        if not development and result['guest_sha256'] != expected:
            raise ValueError('canonical WASM differs; never adopt new guest bytes silently: '+str(result))
        if results and result != results[0]:
            raise ValueError('independent source rebuild differs')
        results.append(result)
        shutil.copy2(guest,out/'mariamem.wasm')
        if development:
            shutil.copy2(linked,out/'linked.wasm')
        for name in ('link.txt','flags.make','CMakeCache.txt'):
            shutil.copy2(work/'artifact'/name,out/name)
        shutil.rmtree(work/'source'); shutil.rmtree(ROOT/'build/unpack')
    commit = subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    record = {'contract':'generated-go-v1','source_commit':commit,'guest_sha256':expected,
              'guest_bytes':(out/'mariamem.wasm').stat().st_size,'repetitions':results,
              'prepared_source':prepared,'toolchain':toolchain,
              'canonical_build_sha256':digest(ROOT/'release/generated-go-build.json')}
    if development:
        if source_identity(ROOT) != identity:
            raise ValueError('source changed during development build')
        record.update(contract=CONTRACT, result='UNQUALIFIED', source_identity=identity,
                      guest_sha256=results[0]['guest_sha256'])
    (out/'guest.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps(record,indent=2))

if __name__ == '__main__':
    main()
