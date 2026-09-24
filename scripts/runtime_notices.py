#!/usr/bin/env python3
"""Generate/verify the pinned Wasmer notice inventory (Python 3.11 for generation).

Normal verification is offline and requires only committed files. --verify-inputs
also rechecks cached upstream inputs; --fetch explicitly permits downloading them.
This tool never approves runtime_notices or rebuilds a runtime.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile
import urllib.request

from common import ROOT, LOCK, digest

INVENTORY = 'release/wasmer-runtime-notices.json'
BUNDLE = 'licenses/Wasmer-Rust-NOTICES.txt'
WORK = ROOT / 'build/runtime-notices'
LEGAL = re.compile(r'^(licen[cs]e|copying|copyright|notice|attributions?)([._-].*)?$', re.I)
FEATURES = ['sys', 'headless-minimal', 'singlepass']
WEBC_DECLARATION = {
    'basis': 'Package metadata license=MIT accepted as the formal license declaration (Task 9b-final).',
    'separate_license_file': 'unavailable upstream',
    'copyright_handling': 'No copyright wording inferred or generated.',
}


def accepted_declaration(package):
    return (package.get('name'), package.get('version'), package.get('license'),
            package.get('source_sha256'), package.get('declaration_acceptance')) == (
        'webc', '12.0.1', 'MIT',
        '715cbfae9eb87236aedca786d0f094e4b513ae5c1bc328a81760d1f9b19f187e',
        WEBC_DECLARATION)



def sha(data):
    return hashlib.sha256(data).hexdigest()


def tree_keys(text):
    return sorted(set(re.findall(r'^(\S+) v(\S+)', text, re.M)))


def read_archive(path):
    with tarfile.open(path) as tar:
        return {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}


def legal_files(files, prefix=''):
    return sorted(n for n in files if n.startswith(prefix) and LEGAL.fullmatch(Path(n).name))


def assemble(records, inputs):
    data = b'Wasmer 7.4.2 runtime dependency notices\n\n'
    data += b'Coverage status and source identities: release/wasmer-runtime-notices.json\n'
    data += b'This collection is not a binary-release approval. See docs/runtime-notices.md.\n'
    for record in records:
        data += ('\n\n=== ' + record['name'] + ' ' + record['version'] + ' ===\n'
                 + 'License metadata: ' + str(record['license']) + '\n'
                 + 'Repository: ' + str(record['repository']) + '\n'
                 + 'Authors: ' + '; '.join(record.get('authors', [])) + '\n').encode()
        if record.get('source_url'):
            data += ('Source: ' + record['source_url'] + '\nSHA256: ' + record['source_sha256'] + '\n').encode()
        for requirement in record.get('notice_requirements', []):
            data += (requirement + '\n').encode()
        for key, value in record.get('declaration_acceptance', {}).items():
            data += (key + ': ' + value + '\n').encode()
        if record.get('missing_reason'):
            data += ('UNRESOLVED: ' + record['missing_reason'] + '\n').encode()
        for notice in record['notices']:
            data += ('\n--- ' + notice['input'] + ':' + notice['path'] + ' ---\n').encode()
            body = inputs[notice['input']][notice['path']]
            if sha(body) != notice['sha256'] or not body.strip():
                raise ValueError('notice content mismatch: ' + notice['path'])
            notice['offset'] = len(data)
            notice['length'] = len(body)
            data += body + b'\n'
    return data


def verify(root=ROOT):
    doc = json.loads((root / INVENTORY).read_text())
    data = (root / BUNDLE).read_bytes()
    if doc['version'] != 1 or sha(data) != doc['bundle_sha256']:
        raise ValueError('notice bundle hash mismatch')
    for path, expected in doc['standalone_notices'].items():
        if digest(root / path) != expected:
            raise ValueError('required standalone notice missing or changed')
    identities = [(p['name'], p['version']) for p in doc['packages']]
    if len(set(identities)) != len(identities):
        raise ValueError('duplicate dependency identity')
    if sha(json.dumps(sorted(identities), separators=(',', ':')).encode()) != doc['dependency_set_sha256']:
        raise ValueError('expected dependency set mismatch')
    if doc['build']['features'] != FEATURES or doc['build']['target'] != 'aarch64-apple-darwin':
        raise ValueError('unexpected runtime build selection')
    known = {e['name']: e for e in json.loads((root / 'release/inputs.lock.json').read_text())['inputs']}
    for name in ('wasmer', 'wasmer-source'):
        if doc['inputs'][name]['sha256'] != known[name]['sha256']:
            raise ValueError('runtime input pin mismatch')
    for p in doc['packages'] + doc['additional_notices']:
        if not p['license'] and not p.get('license_file'):
            raise ValueError('missing license metadata: ' + p['name'])
        if p.get('declaration_acceptance') and not accepted_declaration(p):
            raise ValueError('unreviewed license declaration acceptance')
        if not p['notices'] and not p.get('missing_reason') and not accepted_declaration(p):
            raise ValueError('unaccounted missing notices: ' + p['name'])
        for n in p['notices']:
            body = data[n['offset']:n['offset'] + n['length']]
            if not body.strip() or sha(body) != n['sha256'] or n['input'] not in doc['inputs']:
                raise ValueError('required notice missing or changed: ' + p['name'])
    missing = [p['name'] for p in doc['packages'] if p.get('missing_reason')]
    if sorted(missing) != sorted(doc['missing_notices']):
        raise ValueError('missing notice inventory mismatch')
    if doc['complete'] and missing:
        raise ValueError('notice completeness contradicts missing items')
    review = json.loads((root / 'release/review.json').read_text())['checks']['runtime_notices']
    if review['passed'] and (missing or not doc['complete'] or review['evidence'] != INVENTORY):
        raise ValueError('runtime review approval lacks complete evidence')
    return doc


def verify_inputs(doc, fetch=False):
    import tomllib
    contents = {}
    for key, inp in doc['inputs'].items():
        path = ROOT / inp['cache']
        if not path.exists() and fetch:
            path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(inp['url'], timeout=90) as response:
                content = response.read()
            if sha(content) != inp['sha256']:
                raise ValueError('download hash mismatch: ' + key)
            path.write_bytes(content)
        if digest(path) != inp['sha256']:
            raise ValueError('input hash mismatch: ' + key)
        # Keep only selected members, not the complete dependency source trees.
        wanted = {n['path'] for p in doc['packages'] + doc['additional_notices']
                  for n in p['notices'] if n['input'] == key}
        wanted.update(p['manifest_path'] for p in doc['packages'] if p['input'] == key)
        if key == 'wasmer-source':
            wanted.add('wasmer/Cargo.lock')
        contents[key] = {}
        with tarfile.open(path) as tar:
            for m in tar:
                if m.isfile() and m.name in wanted:
                    contents[key][m.name] = tar.extractfile(m).read()
        for p in doc['packages']:
            if p['input'] != key:
                continue
            body = contents[key][p['manifest_path']]
            if sha(body) != p['manifest_sha256']:
                raise ValueError('crate manifest mismatch: ' + p['name'])
            manifest = tomllib.loads(body.decode())['package']
            if p['source']:
                if (manifest['name'], manifest['version'], manifest.get('license'), manifest.get('license-file')) != (
                        p['name'], p['version'], p['license'], p['license_file']):
                    raise ValueError('crate version/license metadata mismatch: ' + p['name'])
    lock = tomllib.loads(contents['wasmer-source']['wasmer/Cargo.lock'].decode())
    pins = {(p['name'], p['version']): p for p in lock['package']}
    for p in doc['packages']:
        pin = pins[(p['name'], p['version'])]
        if pin.get('source') != p['source']:
            raise ValueError('crate source mismatch: ' + p['name'])
        if p['source'] and pin['checksum'] != doc['inputs'][p['input']]['sha256']:
            raise ValueError('crate checksum mismatch: ' + p['name'])
    if sha(assemble(doc['packages'] + doc['additional_notices'], contents)) != doc['bundle_sha256']:
        raise ValueError('notice regeneration differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-inputs', action='store_true')
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--cargo-tree', type=Path, help='compare a fresh normal-edge Cargo tree with expected dependencies')
    parser.add_argument('--native-dir', type=Path, help='check the exact distributed wasmer-headless bytes')
    args = parser.parse_args()
    doc = verify()
    if args.cargo_tree and tree_keys(args.cargo_tree.read_text()) != sorted((p['name'], p['version']) for p in doc['packages']):
        raise ValueError('Cargo dependency set differs from reviewed inventory')
    if args.native_dir and digest(args.native_dir / 'wasmer-headless') != doc['runtime_sha256']:
        raise ValueError('runtime binary differs from reviewed inventory')
    if args.verify_inputs or args.fetch:
        verify_inputs(doc, args.fetch)
    print(json.dumps({'verified': True, 'packages': len(doc['packages']),
                      'missing_notices': doc['missing_notices'], 'complete': doc['complete'],
                      'runtime_notices_passed': json.loads((ROOT / 'release/review.json').read_text())['checks']['runtime_notices']['passed']}))


if __name__ == '__main__':
    main()
