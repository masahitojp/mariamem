#!/usr/bin/env python3
"""Exact-input artifact reuse for measurements only; release builds stay strict."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from common import ROOT, LOCK, digest
from native_target import target_metadata, platform_fields
from release_version import PYTHON_VERSION

RECIPE = ('scripts/prepare_guest.py', 'scripts/guest_init_hooks.py',
          'scripts/build_guest_wasm.py', 'scripts/install_guest_toolchain.py',
          'scripts/common.py', 'scripts/benchmark_artifacts.py', 'scripts/guest_experiment.py',
          'scripts/install_guest_host_tools.sh')


def hash_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def guest_inputs(root=ROOT, commit=None):
    if commit:
        files = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit, 'guest'],
                                        cwd=root, text=True).splitlines()
        read = lambda name: subprocess.check_output(['git', 'show', f'{commit}:{name}'], cwd=root)
    else:
        files = [p.relative_to(root).as_posix() for p in sorted((root / 'guest').rglob('*')) if p.is_file()]
        read = lambda name: (root / name).read_bytes()
    lock = json.loads(read('release/inputs.lock.json'))
    guest_lock = {'inputs': [entry for entry in lock['inputs'] if entry['name'] in
                  ('lite4mariadb', 'libmariadb', 'wolfssl', 'pcre2', 'libfmt')],
                  'pristine_files': lock['pristine_files'],
                  'toolchain': {name: lock['toolchain'][name] for name in
                    ('wasixcc', 'wasixcc_linux_x86_64', 'llvm', 'binaryen',
                     'wasix_sysroot', 'wasix_sysroot_variant')}}
    return {'guest_lock': guest_lock, 'schema': 1, 'host': 'ubuntu24.04-x86_64', 'target': 'wasm32/WASIX',
            'jobs': 3, 'files': {name: hashlib.sha256(read(name)).hexdigest()
                               for name in sorted(set(files) | set(RECIPE))}}


def aot_inputs(wasm_dir, target_name, root=ROOT):
    target = target_metadata(target_name, root)
    pin = next(p for p in LOCK['inputs'] if p['name'] == target['runtime_input'])
    from compile_guest_aot import compile_command
    return {'schema': 1, 'wasm_sha256': digest(wasm_dir / 'mariamem.wasm'),
            'handoff_sha256': digest(wasm_dir / 'provenance.json'),
            'target': target, 'wasmer': LOCK['toolchain']['wasmer'], 'runtime': pin,
            'compile_flags': compile_command('wasmer', 'wasm', 'aot', target)[5:],
            'package_version': PYTHON_VERSION,
            'recipe': {name: digest(root / name) for name in
                       ('scripts/compile_guest_aot.py', 'scripts/native_target.py',
                        'scripts/common.py', 'scripts/benchmark_artifacts.py')}}


def stamp(directory, inputs):
    """Seal only outputs built/verified by the canonical scripts; never re-stamp a hit."""
    files = sorted(p.name for p in directory.iterdir() if p.is_file() and p.name != 'reuse.json')
    record = {'version': 1, 'build_checkout': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'inputs': inputs,
        'identity': hash_json(inputs), 'files': {name: digest(directory / name) for name in files}}
    (directory / 'reuse.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')


def verify_seal(directory, expected):
    record = json.loads((directory / 'reuse.json').read_text())
    if record['version'] != 1 or record['inputs'] != expected or record['identity'] != hash_json(expected):
        raise ValueError('benchmark artifact input identity mismatch; rebuild required')
    actual = {p.name: digest(p) for p in directory.iterdir() if p.is_file() and p.name != 'reuse.json'}
    if actual != record['files']:
        raise ValueError('benchmark artifact file/hash mismatch; refusing cache contents')
    return record


def verify_wasm(directory):
    from compile_guest_aot import verify_handoff
    seal = verify_seal(directory, guest_inputs())
    # An earlier build is allowed only if its recorded checkout has exactly the
    # same relevant inputs. Do not relabel the original build as this checkout.
    if guest_inputs(commit=seal['build_checkout']) != seal['inputs']:
        raise ValueError('original guest build checkout inputs differ')
    _, _, record = verify_handoff(directory, check_source_commit=False, check_input_lock=False)
    lock_bytes = subprocess.check_output(
        ['git', 'show', f"{seal['build_checkout']}:release/inputs.lock.json"], cwd=ROOT)
    original_lock = hashlib.sha256(lock_bytes).hexdigest()
    if any(part['inputs_lock_sha256'] != original_lock for part in
           (record, record['prepared_source'], record['toolchain'])):
        raise ValueError('original guest lock provenance differs')
    if record.get('build_configuration') != {'jobs': 3}:
        raise ValueError('reused guest build configuration differs')
    if record['source_commit'] != seal['build_checkout']:
        raise ValueError('original guest source commit differs from reuse seal')
    overlays = {p.name: digest(p) for p in sorted((ROOT / 'guest').iterdir()) if p.is_file()}
    if record['prepared_source']['overlays'] != overlays:
        raise ValueError('reused prepared guest patches/overlays differ')
    tool = record['toolchain']
    pin = LOCK['toolchain']['wasixcc_linux_x86_64']
    if (tool['wasixcc_archive_sha256'] != pin['sha256'] or tool['wasixcc_archive_url'] != pin['url']
            or tool['wasixcc_version'] != LOCK['toolchain']['wasixcc']):
        raise ValueError('reused guest toolchain differs')
    for field, pin_field in (('llvm_tag', 'llvm'), ('binaryen_tag', 'binaryen'),
                             ('sysroot_tag', 'wasix_sysroot'), ('sysroot_variant', 'wasix_sysroot_variant')):
        if tool[field] != LOCK['toolchain'][pin_field]:
            raise ValueError(f'reused guest toolchain differs: {field}')
    reviewed = json.loads((ROOT / 'release/guest-source-provenance.json').read_text())['sysroot']
    if (tool['sysroot']['inventory_sha256'] != reviewed['comparison']['inventory_sha256']
            or tool['sysroot_major_libraries_sha256'] != reviewed['major_library_sha256']):
        raise ValueError('reused guest sysroot provenance differs')
    return record


def verify_aot(directory, wasm_dir, target_name):
    verify_wasm(wasm_dir)
    expected = aot_inputs(wasm_dir, target_name)
    seal = verify_seal(directory, expected)
    # Verify the producing checkout's AOT recipe too, not just its output seal.
    for name, sha in expected['recipe'].items():
        data = subprocess.check_output(['git', 'show', f"{seal['build_checkout']}:{name}"], cwd=ROOT)
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError('original AOT recipe differs')
    record = json.loads((directory / 'provenance.json').read_text())
    manifest = json.loads((directory / 'manifest.json').read_text())
    sidecar = json.loads((directory / 'mariamem.wasmu.json').read_text())
    wasm = json.loads((wasm_dir / 'provenance.json').read_text())
    if (record['wasm_handoff_provenance_sha256'] != digest(wasm_dir / 'provenance.json')
            or record['source_commit'] != wasm['source_commit']
            or record['wasm_sha256_verified'] != expected['wasm_sha256']):
        raise ValueError('AOT handoff provenance mismatch')
    if (record['aot_sha256'] != digest(directory / 'mariamem.wasmu')
            or record['aot_bytes'] != (directory / 'mariamem.wasmu').stat().st_size
            or record['native_manifest_sha256'] != digest(directory / 'manifest.json')
            or record['wasmer_archive_sha256'] != expected['runtime']['sha256']
            or manifest['package_version'] != expected['package_version']
            or manifest['platform'] != target_name):
        raise ValueError('AOT artifact/runtime/version mismatch')
    if (manifest['version'] != 1 or sidecar['snapshot_version'] != 1
            or record['wasmer_version'] != 'wasmer ' + expected['wasmer']):
        raise ValueError('AOT format/Wasmer version mismatch')
    for name, value in platform_fields(target_metadata(target_name, ROOT)).items():
        if manifest.get(name) != value:
            raise ValueError(f'AOT platform metadata mismatch: {name}')
    notice_file = 'wasmer-runtime-notices.json' if target_name == 'darwin-arm64' else 'wasmer-linux-runtime-notices.json'
    notice = json.loads((ROOT / 'release' / notice_file).read_text())
    if digest(directory / 'wasmer-headless') != notice['runtime_sha256']:
        raise ValueError('AOT runtime differs from reviewed runtime hash')
    for name, sha in manifest['sha256'].items():
        if digest(directory / name) != sha:
            raise ValueError(f'AOT manifest hash mismatch: {name}')
    if (sidecar['module_sha256'] != record['aot_sha256']
            or sidecar['wasm_sha256'] != expected['wasm_sha256']
            or record['headless_executable_sha256'] != digest(directory / 'wasmer-headless')):
        raise ValueError('AOT sidecar/runtime mismatch')
    if target_name == 'ubuntu24.04-x86_64' and (
            record['aot_cpu_features'] != ['sse2', 'ssse3']
            or record['aot_target_triple'] != 'x86_64-unknown-linux-gnu'):
        raise ValueError('AOT CPU baseline mismatch')
    (directory / 'wasmer-headless').chmod((directory / 'wasmer-headless').stat().st_mode | 0o111)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['key', 'seal', 'verify'])
    parser.add_argument('stage', choices=['wasm', 'aot'])
    parser.add_argument('--target', choices=['darwin-arm64', 'ubuntu24.04-x86_64'])
    args = parser.parse_args()
    wasm_dir = ROOT / 'build/guest-wasm'
    if args.stage == 'aot' and not args.target:
        parser.error('AOT requires --target')
    inputs = guest_inputs() if args.stage == 'wasm' else aot_inputs(wasm_dir, args.target)
    directory = wasm_dir if args.stage == 'wasm' else ROOT / 'build/guest-aot'
    if args.operation == 'key':
        print(f"measurement-{args.stage}-v1-{hash_json(inputs)}")
    else:
        if args.operation == 'seal':
            # A cache miss must come through the canonical fresh build path.
            if args.stage == 'wasm':
                from compile_guest_aot import verify_handoff
                verify_handoff(directory)
            stamp(directory, inputs)
        result = verify_wasm(directory) if args.stage == 'wasm' else verify_aot(directory, wasm_dir, args.target)
        print(json.dumps({'stage': args.stage, 'identity': hash_json(inputs),
                          'original_build_commit': json.loads((directory / 'reuse.json').read_text())['build_checkout'],
                          'guest_source_commit': result['source_commit'],
                          'sha256': result['wasm_sha256'] if args.stage == 'wasm' else result['aot_sha256']}))


if __name__ == '__main__':
    main()
