#!/usr/bin/env python3
"""Verify Ubuntu Wasmer notices, reusing the reviewed common inventory plus Linux additions."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile
import urllib.request

from common import ROOT, LOCK, digest
from runtime_notices import verify as verify_common, tree_keys, legal_files

INVENTORY = 'release/wasmer-linux-runtime-notices.json'
BUNDLE = 'licenses/Wasmer-Linux-NOTICES.txt'
TARGET = 'x86_64-unknown-linux-gnu'


def verify(root=ROOT):
    base = verify_common(root)
    record = json.loads((root / INVENTORY).read_text())
    runtime_pin = next(i for i in json.loads((root / 'release/inputs.lock.json').read_text())['inputs']
                       if i['name'] == 'wasmer-linux-x86_64')
    source_pin = next(i for i in json.loads((root / 'release/inputs.lock.json').read_text())['inputs'] if i['name'] == 'wasmer-source')
    if record['wasmer_source_sha256'] != source_pin['sha256']:
        raise ValueError('Linux Wasmer source pin mismatch')
    if record['runtime_archive_sha256'] != runtime_pin['sha256'] or record['target'] != TARGET:
        raise ValueError('Linux runtime pin/target mismatch')
    if record['common_inventory_sha256'] != digest(root / 'release/wasmer-runtime-notices.json'):
        raise ValueError('Linux common notice inventory changed')
    data = (root / BUNDLE).read_bytes()
    if hashlib.sha256(data).hexdigest() != record['bundle_sha256']:
        raise ValueError('Linux notice bundle mismatch')
    if record['features'] != base['build']['features'] or record['rust_commit'] != base['binary_observed_rust_commit']:
        raise ValueError('Linux runtime build inputs differ')
    common = {(p['name'], p['version']) for p in base['packages']}
    extra = {(p['name'], p['version']) for p in record['additional_packages']}
    expected = {tuple(p) for p in record['dependency_set']}
    if len(expected) != len(record['dependency_set']) or not expected <= common | extra:
        raise ValueError('Linux dependency notice coverage incomplete')
    if extra != expected - common:
        raise ValueError('Linux supplemental dependencies differ')
    for p in record['additional_packages']:
        if not p['license'] or not p['notices']:
            raise ValueError('Linux dependency license missing')
        for n in p['notices']:
            body = data[n['offset']:n['offset'] + n['length']]
            if not body or hashlib.sha256(body).hexdigest() != n['sha256']:
                raise ValueError('Linux dependency notice changed')
    for n in record['upstream_notices']:
        body = data[n['offset']:n['offset'] + n['length']]
        if hashlib.sha256(body).hexdigest() != n['sha256']:
            raise ValueError('Linux upstream notice changed')
    if not record['complete'] or record.get('missing_notices') != []:
        raise ValueError('Linux runtime notices incomplete')
    return record


def collect(tree, root=ROOT):
    import tomllib
    base = verify_common(root)
    dependency_set = tree_keys(tree.read_text())
    if not dependency_set:
        raise ValueError('empty Linux Cargo graph')
    runtime = root / 'build/downloads/wasmer-linux-amd64.tar.gz'
    runtime_pin = next(i for i in LOCK['inputs'] if i['name'] == 'wasmer-linux-x86_64')
    if digest(runtime) != runtime_pin['sha256']:
        raise ValueError('Linux Wasmer archive differs')
    source_archive = root / 'build/downloads/wasmer-full-source.tar.gz'
    source_pin = next(i for i in LOCK['inputs'] if i['name'] == 'wasmer-source')
    if digest(source_archive) != source_pin['sha256']:
        raise ValueError('Linux Wasmer source archive differs')
    with tarfile.open(source_archive) as archive:
        cargo_lock = archive.extractfile('wasmer/Cargo.lock').read()
    pins = {(p['name'], p['version']): p for p in tomllib.loads(cargo_lock.decode())['package']}
    common = {(p['name'], p['version']) for p in base['packages']}
    data = bytearray(b'Wasmer 7.4.2 Linux x86_64 supplementary notices\nCommon dependencies and Rust standard library notices: Wasmer-Rust-NOTICES.txt\n\n')
    def append_notice(name, body):
        data.extend(('\n=== ' + name + ' ===\n').encode())
        item = {'path': name, 'sha256': hashlib.sha256(body).hexdigest(), 'offset': len(data), 'length': len(body)}
        data.extend(body + b'\n')
        return item
    additions = []
    cache = root / 'build/runtime-notices/linux-inputs'
    cache.mkdir(parents=True, exist_ok=True)
    for name, version in sorted(set(dependency_set) - common):
        pin = pins[name, version]
        if not pin.get('source', '').startswith('registry+') or not pin.get('checksum'):
            raise ValueError('unrecognized Linux dependency source: ' + name)
        url = f'https://static.crates.io/crates/{name}/{name}-{version}.crate'
        path = cache / f'{name}-{version}.crate'
        if not path.exists():
            with urllib.request.urlopen(url, timeout=120) as stream:
                path.write_bytes(stream.read())
        if digest(path) != pin['checksum']:
            raise ValueError('Linux crate checksum mismatch')
        with tarfile.open(path) as archive:
            files = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
        metadata = tomllib.loads(files[f'{name}-{version}/Cargo.toml'].decode())['package']
        notices = [append_notice(n, files[n]) for n in legal_files(files)]
        supplemental = None
        if not notices:
            vcs = json.loads(files[f'{name}-{version}/.cargo_vcs_info.json'])
            crate_revision = vcs['git']['sha1']
            # These published crate vcs commits are unavailable upstream; the official
            # v0.4.8/sys-v4.0.0 tags share this pinned revision and license declarations.
            revision = 'c9d0bd5c96581f39d7430aef65baa33bc25d054f' if (name,version) in {('perf-event','0.4.8'),('perf-event-open-sys','4.0.0')} else crate_revision
            repository = metadata.get('repository', '').removesuffix('.git')
            if name == 'perf-event-open-sys':
                repository = 'https://github.com/jimblandy/perf-event'
            if not repository.startswith('https://github.com/') or not re.fullmatch('[0-9a-f]{40}', revision):
                raise ValueError('unavailable pinned upstream license: ' + name)
            source_url = repository.replace('https://github.com/', 'https://codeload.github.com/') + '/tar.gz/' + revision
            source_path = cache / f'{name}-{revision}.tar.gz'
            if not source_path.exists():
                with urllib.request.urlopen(source_url, timeout=120) as stream:
                    source_path.write_bytes(stream.read())
            with tarfile.open(source_path) as archive:
                legal = {m.name: archive.extractfile(m).read() for m in archive if m.isfile() and legal_files({m.name: None})}
            notices = [append_notice(n, b) for n,b in sorted(legal.items())]
            if not notices:
                raise ValueError('No distributable pinned upstream license: ' + name)
            supplemental = {'source_url': source_url, 'source_sha256': digest(source_path), 'revision': revision,
                            'crate_vcs_revision': crate_revision,
                            'basis': 'official crate version tag supplies upstream license texts; crate vcs revision recorded separately' if revision != crate_revision else 'crate .cargo_vcs_info.json immutable source revision'}
        additions.append({'name': name, 'version': version, 'license': metadata.get('license'),
                          'source': pin['source'], 'source_url': url, 'source_sha256': pin['checksum'], 'notices': notices,
                          'upstream_license_source': supplemental})
    with tarfile.open(runtime) as archive:
        binary = archive.extractfile('bin/wasmer-headless').read()
        upstream = [append_notice(name, archive.extractfile(name).read()) for name in ('LICENSE', 'ATTRIBUTIONS')]
    observed = sorted(set((a.decode(), v.decode()) for a, v in re.findall(rb'([A-Za-z0-9_-]+)-([0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9_.+-]*))/src/', binary)))
    observed_rust = set(c.decode() for c in re.findall(rb'rustc/([a-f0-9]{40})', binary))
    if observed_rust != {base['binary_observed_rust_commit']}:
        raise ValueError('Linux Rust standard library build differs from reviewed notices')
    # These are Rust stdlib components already covered by upstream COPYRIGHT-library.html.
    if set(observed) - set(dependency_set) - {('hashbrown', '0.16.1'), ('rustc-demangle', '0.1.27')}:
        raise ValueError('unaccounted Linux binary crate')
    record = {'version': 1, 'complete': True, 'missing_notices': [], 'target': TARGET, 'features': base['build']['features'],
              'runtime_archive_sha256': digest(runtime), 'runtime_sha256': hashlib.sha256(binary).hexdigest(),
              'wasmer_source_sha256': next(i for i in LOCK['inputs'] if i['name'] == 'wasmer-source')['sha256'],
              'cargo_lock_sha256': hashlib.sha256(cargo_lock).hexdigest(),
              'cargo_tree_sha256': digest(tree), 'dependency_set': dependency_set,
              'common_inventory_sha256': digest(root / 'release/wasmer-runtime-notices.json'),
              'additional_packages': additions, 'upstream_notices': upstream,
              'rust_commit': next(iter(observed_rust)), 'binary_observed_crates': observed,
              'bundle_sha256': hashlib.sha256(data).hexdigest(),
              'basis': 'Pinned upstream minimal-headless Cargo selection; conservative normal dependency graph, not a post-LTO object inventory.'}
    (root / BUNDLE).write_bytes(data)
    (root / INVENTORY).write_text(json.dumps(record, indent=2) + '\n')
    return verify(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-tree', type=Path)
    args = parser.parse_args()
    record = collect(args.collect_tree) if args.collect_tree else verify()
    print(json.dumps({'complete': record['complete'], 'runtime_sha256': record['runtime_sha256']}))
