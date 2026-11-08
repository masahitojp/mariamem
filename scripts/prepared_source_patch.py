"""Exact-input prepared API repair proofs; canonical series or isolated experiment."""
import json
from pathlib import Path
import re
import subprocess

from common import ROOT, digest


def check_functions(source, root, version):
    """Keep component proofs bound to the actual complete source, not a replica."""
    profile = json.loads((Path(root) / 'guest/prepared_source_patch.json').read_text()).get('profile')
    # The native profile must leave every legacy C API function UNMODIFIED.
    if profile == 'native-text':
        version = 'before'
    for filename in ['prepared-p2-source-functions.json','prepared-param-order-functions.json']:
        fixture = json.loads((root / 'tests/fixtures' / filename).read_text())
        text = (source / fixture['file']).read_text()
        for name, body in fixture[version].items():
            expression = r'^(?:static void|static bool|int STDCALL|my_bool STDCALL) ' + re.escape(name) + r'\([^\n]*\)\n\{.*?^\}'
            found = re.search(expression, text, re.M | re.S)
            if not found or found.group() != body:
                raise ValueError('prepared source proof changed: ' + name)


def inputs(root=ROOT):
    root = Path(root)
    pin = json.loads((root / 'guest/prepared_source_patch.json').read_text())
    source = json.loads((root / 'guest/input.json').read_text())
    patch_file = pin.get('patch_file', 'guest/experimental.patch')
    profile = source.get('prepared_profile')
    profiles = {'legacy-full': 'guest/patches/13.0.2-prepared.patch',
                'native-text': 'guest/patches/13.0.2-native-prepared.patch'}
    if profile not in profiles or pin.get('profile') != profile or patch_file != profiles[profile]:
        raise ValueError('missing or mismatched explicit prepared profile')
    if (profile == 'native-text') != ('native_overlay' in source):
        raise ValueError('prepared profile differs from guest route')
    if patch_file not in profiles.values():
        raise ValueError('unregistered prepared source patch')
    patch = root / patch_file
    if patch_file != 'guest/experimental.patch':
        entries = [e for e in source.get('patches', []) if e['file'] == patch_file]
        if (len(entries) != 1 or entries[0]['sha256'] != pin['patch_sha256'] or
                entries[0]['before_sha256'] != {i['file']: i['before_sha256'] for i in pin['files']} or
                entries[0]['after_sha256'] != {i['file']: i['after_sha256'] for i in pin['files']}):
            raise ValueError('canonical prepared source series differs')
    names = [item['file'] for item in pin['files']]
    expected_names = ['sql/sql_prepare.cc', 'libmysqld/libmysql.c', 'libmysqld/lib_sql.cc']
    if profile == 'native-text':
        expected_names.remove('libmysqld/libmysql.c')
    portability = next((item for item in source.get('patches', [])
                        if item['file'] == 'guest/patches/common-portability.patch'), {})
    if (pin['source_commit'] != source['source_commit'] or
            names != expected_names or
            (pin.get('unchanged_files', {}).get('libmysqld/libmysql.c') if profile == 'native-text'
             else pin['files'][1]['before_sha256']) != portability.get('after_sha256', {}).get('libmysqld/libmysql.c') or
            patch.is_symlink() or digest(patch) != pin['patch_sha256'] or
            digest(root / 'tests/fixtures/prepared-p2-source-functions.json') != pin['component_fixture_sha256'] or
            digest(root / 'tests/fixtures/prepared-param-order-functions.json') != pin['parameter_fixture_sha256'] or
            re.findall(r'^\+\+\+ b/(.+)$', patch.read_text(), re.M) != names):
        raise ValueError('prepared source patch inputs changed')
    return pin


def check_profile_source(source, root=ROOT):
    """Check all full images, including the deliberately unchanged C API file."""
    pin = inputs(root)
    for item in pin['files']:
        if digest(Path(source) / item['file']) != item['after_sha256']:
            raise ValueError('prepared profile postimage changed: ' + item['file'])
    for name, expected in pin.get('unchanged_files', {}).items():
        if digest(Path(source) / name) != expected:
            raise ValueError('prepared profile unchanged file changed: ' + name)
    check_functions(source, root, 'after')


def apply(source, root=ROOT):
    root, source = Path(root), Path(source)
    pin = inputs(root)
    # Check every complete preimage before mutating any source file.
    for item in pin['files']:
        target = source / item['file']
        if target.is_symlink() or digest(target) != item['before_sha256']:
            raise ValueError('prepared source patch preimage changed: ' + item['file'])
    check_functions(source, root, 'before')
    subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i',
                    str((root / pin.get('patch_file', 'guest/experimental.patch')).resolve())], cwd=source, check=True)
    for item in pin['files']:
        if digest(source / item['file']) != item['after_sha256']:
            raise ValueError('prepared source patch postimage changed: ' + item['file'])
    check_functions(source, root, 'after')
    return pin


if __name__ == '__main__':
    inputs()
    print('PASS: exact prepared source patch inputs')
