"""Exact-input experimental prepared API repairs; never canonical adoption."""
import json
from pathlib import Path
import re
import subprocess

from common import ROOT, digest


def check_functions(source, root, version):
    """Keep component proofs bound to the actual complete source, not a replica."""
    for filename in ['prepared-p2-source-functions.json','prepared-param-order-functions.json']:
        fixture = json.loads((root / 'tests/fixtures' / filename).read_text())
        text = (source / fixture['file']).read_text()
        for name, body in fixture[version].items():
            expression = r'^(?:static void|static bool|int STDCALL|my_bool STDCALL) ' + re.escape(name) + r'\([^\n]*\)\n\{.*?^\}'
            found = re.search(expression, text, re.M | re.S)
            if not found or found.group() != body:
                raise ValueError('experimental prepared source proof changed: ' + name)


def inputs(root=ROOT):
    root = Path(root)
    pin = json.loads((root / 'guest/prepared_source_patch.json').read_text())
    source = json.loads((root / 'guest/input.json').read_text())
    patch = root / 'guest/experimental.patch'
    names = [item['file'] for item in pin['files']]
    portability = next((item for item in source.get('patches', [])
                        if item['file'] == 'guest/patches/common-portability.patch'), {})
    if (pin['source_commit'] != source['source_commit'] or
            names != ['sql/sql_prepare.cc', 'libmysqld/libmysql.c', 'libmysqld/lib_sql.cc'] or
            pin['files'][1]['before_sha256'] != portability.get('after_sha256', {}).get('libmysqld/libmysql.c') or
            patch.is_symlink() or digest(patch) != pin['patch_sha256'] or
            digest(root / 'tests/fixtures/prepared-p2-source-functions.json') != pin['component_fixture_sha256'] or
            digest(root / 'tests/fixtures/prepared-param-order-functions.json') != pin['parameter_fixture_sha256'] or
            re.findall(r'^\+\+\+ b/(.+)$', patch.read_text(), re.M) != names):
        raise ValueError('experimental prepared source patch inputs changed')
    return pin


def apply(source, root=ROOT):
    root, source = Path(root), Path(source)
    pin = inputs(root)
    # Check every complete preimage before mutating any source file.
    for item in pin['files']:
        target = source / item['file']
        if target.is_symlink() or digest(target) != item['before_sha256']:
            raise ValueError('experimental prepared source patch preimage changed: ' + item['file'])
    check_functions(source, root, 'before')
    subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i',
                    str((root / 'guest/experimental.patch').resolve())], cwd=source, check=True)
    for item in pin['files']:
        if digest(source / item['file']) != item['after_sha256']:
            raise ValueError('experimental prepared source patch postimage changed: ' + item['file'])
    check_functions(source, root, 'after')
    return pin


if __name__ == '__main__':
    inputs()
    print('PASS: exact experimental prepared source patch inputs')
