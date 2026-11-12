"""Build an isolated experimental host from the exact successful UCA guest.

No C rebuild, canonical binding edit, guest input relabel or release output.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import uca_copy_bindings as binding

HERE = Path(__file__).resolve().parents[1]
ARCHIVES = {
    'guest': '86effbaea48a78e7fabc53ff5003d21cb1510d19343e913386936c74ef80a221',
    'translation': '54f16c29db3c581ed7d27398dae48d122fd1ee7aef3d9b29ee0fa0b451028c40',
}


def extract_guest(archive, output):
    with zipfile.ZipFile(archive) as z:
        expected = {'CMakeCache.txt', 'guest.json', 'flags.make', 'link.txt', 'linked.wasm', 'mariamem.wasm'}
        if set(z.namelist()) != expected or len(z.namelist()) != len(expected):
            raise ValueError('unexpected guest archive members')
        output.mkdir()
        for name in expected:
            (output/name).write_bytes(z.read(name))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--origin', type=Path, required=True)
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    origin = a.origin.resolve()
    sys.path.insert(0, str(origin/'scripts'))
    from dev_guest import (source_identity, verify_guest, verify_translation,
                           inventory, external_output, CONTRACT, write)
    from build_generated_guest import download
    from common import digest
    execution_identity = source_identity(HERE)
    identity = source_identity(origin)
    if identity['commit'] != binding.ORIGIN:
        raise ValueError('requires the exact immutable guest-origin checkout')
    for name, sha in ARCHIVES.items():
        if digest(a.artifacts/(name+'.zip')) != sha:
            raise ValueError('artifact ZIP mismatch: '+name)
    out = external_output(HERE, a.output.resolve())
    if out.is_relative_to(origin) or origin.is_relative_to(out):
        raise ValueError('output overlaps origin checkout')
    out.mkdir()
    try:
        guest = out/'guest'
        extract_guest(a.artifacts/'guest.zip', guest)
        record = verify_guest(origin, guest)
        if record['guest_sha256'] != binding.GUEST:
            raise ValueError('unreviewed guest')
        with zipfile.ZipFile(a.artifacts/'translation.zip') as z:
            expected = json.loads(z.read('assessment.json'))
        if expected['source_commit'] != binding.ORIGIN or expected['guest_sha256'] != binding.GUEST:
            raise ValueError('translation assessment origin mismatch')
        # Reproduce the small converter/adapter stage so the existing dev verifier
        # sees all its required files, including the converter binary. No C build.
        tools = json.loads((origin/'release/generated-go-toolchain.json').read_text())
        converter = download(tools['archives']['converter'], out/'downloads')
        spike = origin/'benchmarks/spikes/generated-go-integration'
        env = dict(os.environ, GOTOOLCHAIN='go1.26.10', GOWORK='off', GOENV='off', PYTHONDONTWRITEBYTECODE='1')
        def run(cmd, **kwargs):
            subprocess.run(list(map(str, cmd)), env=env, check=True, **kwargs)
        translation = out/'translation'
        run([sys.executable, spike/'translate_guest.py', '--guest', guest/'mariamem.wasm',
             '--guest-sha256', binding.GUEST, '--converter-archive', converter, '--output', translation])
        verify_translation(origin, translation, binding.GUEST)
        run([sys.executable, spike/'setup_candidate.py', '--source-only', '--source-module', translation/'module',
             '--guest', guest/'mariamem.wasm', '--input-manifest', translation/'input-manifest.json', '--output', out/'candidate'])
        module = out/'candidate/module'
        if inventory(module) != expected['candidate_inventory']:
            raise ValueError('reproduced source differs from successful CI artifact')
        inputs = {'contract': CONTRACT, 'result': 'UNQUALIFIED', 'guest_sha256': binding.GUEST,
                  'source_inventory': inventory(module), 'data_sha256': digest(module/'generated/data.bin'),
                  'candidate_files_sha256': {p.relative_to(module).as_posix(): digest(p)
                       for suffix in ('*.go', '*.s') for p in module.rglob(suffix)},
                  'guest_directory': str(guest), 'translation_directory': str(translation),
                  'guest_record_sha256': digest(guest/'guest.json'),
                  'translation_record_sha256': digest(translation/'input-manifest.json')}
        write(out/'installation-inputs.json', inputs)
        # Only this process selects the reviewed experimental pins. Every original
        # complete-body/table validator and transformation still executes.
        sys.modules.update(binding.load(origin))
        spec = importlib.util.spec_from_file_location('uca_experimental_installer', origin/'scripts/generate_runtime.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        staged = out/'generatedgo'
        sys.argv = ['generate_runtime.py', '--source-module', str(module), '--development-input',
                    str(out/'installation-inputs.json'), '--output', str(staged)]
        installer.main()
        product = out/'product'
        for name in identity['files_sha256']:
            if not name.startswith('internal/generatedgo/'):
                dest = product/name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin/name, dest)
        shutil.move(staged, product/'internal/generatedgo')
        kind = product/'internal/runtimekind/kind.go'
        text = kind.read_text()
        old = 'const GuestSHA256 = "'+binding.CANONICAL+'"'
        if text.count(old) != 1:
            raise ValueError('host guest identity anchor changed')
        kind.write_text(text.replace(old, 'const GuestSHA256 = "'+binding.GUEST+'"'))
        shutil.copy2(HERE/'tests/uca_copy_actual_test.go.txt', product/'internal/generatedgo/uca_copy_actual_test.go')
        # Canonical page-validation tests contain guest-address fixture setup.
        # Rebind the isolated test copy too; never weaken the corruption oracle.
        crc_test = product/'internal/generatedgo/code/p4/crc32c_test.go'
        crc_test.write_text(binding.crc_test_source(crc_test.read_text()))
        host = out/'mariamem-uca-copy-host'
        run(['go', 'build', '-p', '1', '-trimpath', '-buildvcs=false', '-o', host, './cmd/mariamem-host'], cwd=product)
        info = json.loads(subprocess.check_output([host, '--snapshot-info'], env=env, text=True))
        if info['wasm_sha256'] != binding.GUEST:
            raise ValueError('wrong compiled guest identity')
        if source_identity(origin) != identity or source_identity(HERE) != execution_identity:
            raise ValueError('source changed during installation')
        write(out/'installation.json', {'result': 'UNQUALIFIED_HOST_BUILT', 'guest_source_commit': binding.ORIGIN,
              'execution_source_commit': execution_identity['commit'], 'guest_sha256': binding.GUEST,
              'host_sha256': digest(host), 'canonical_adapters_unchanged': True,
              'crc_fixture_origin_sha256': binding.CRC_TEST_SOURCE_SHA256,
              'crc_fixture_experimental_sha256': digest(crc_test),
              'crc_fixture_relocations': binding.CRC_TEST_RELOCATIONS,
              'reproduced_candidate_inventory_matches_ci': True,
              'generated_inventory': inventory(product/'internal/generatedgo'), 'runtime_acceptance': False})
    except BaseException as exc:
        write(out/'failure.json', {'result':'FAIL', 'guest_source_commit':binding.ORIGIN,
              'execution_source_commit':execution_identity['commit'], 'error':type(exc).__name__, 'message':str(exc)})
        raise


if __name__ == '__main__':
    main()
