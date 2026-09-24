#!/usr/bin/env python3
"""Collect notices from Cargo metadata/tree and checksum-verified pinned archives.

Requires Python 3.11. Inputs are prepared as documented in docs/runtime-notices.md.
No compilation, dependency update, or review approval is performed.
"""
import json
from pathlib import Path
import shutil
import tarfile
import tomllib

from common import ROOT, LOCK, digest
from runtime_notices import WORK, INVENTORY, BUNDLE, FEATURES, sha, tree_keys, legal_files, assemble, WEBC_DECLARATION, accepted_declaration


def main():
    metadata = json.loads((WORK / 'metadata.json').read_text())
    selected = tree_keys((WORK / 'tree.txt').read_text())
    runtime = set(tree_keys((WORK / 'runtime-tree.txt').read_text()))
    inputs, contents = {}, {}

    def add_input(key, path, url, expected):
        if digest(path) != expected:
            raise ValueError('input hash mismatch: ' + key)
        inputs[key] = {'url': url, 'sha256': expected, 'cache': path.relative_to(ROOT).as_posix()}
        contents[key] = {}
        # Retain legal documents and Cargo manifests only.
        with tarfile.open(path) as tar:
            for m in tar:
                if m.isfile() and (legal_files({m.name: None}) or m.name.endswith(('Cargo.toml', 'Cargo.lock', 'COPYRIGHT-library.html'))):
                    contents[key][m.name] = tar.extractfile(m).read()
        return key

    for name in ('wasmer', 'wasmer-source'):
        entry = next(e for e in LOCK['inputs'] if e['name'] == name)
        add_input(name, ROOT / 'build/downloads' / entry['file'], entry['url'], entry['sha256'])
    lock = tomllib.loads(contents['wasmer-source']['wasmer/Cargo.lock'].decode())
    pins = {(p['name'], p['version']): p for p in lock['package']}
    previous = json.loads((ROOT / INVENTORY).read_text())
    supplements = previous['inputs']
    for key in ('cynic', 'dynasm', 'wild', 'symbolic', 'wai', 'wai-parser'):
        e = supplements[key]
        add_input(key, WORK / (key + '.tar.gz'), e['url'], e['sha256'])
    rust_path = WORK / 'rustc.tar.xz'
    add_input('rust-1.95.0', rust_path,
              'https://static.rust-lang.org/dist/rustc-1.95.0-aarch64-apple-darwin.tar.xz', previous['inputs']['rust-1.95.0']['sha256'])
    mapped = {'symbolic-common': 'symbolic', 'dynasm': 'dynasm', 'dynasmrt': 'dynasm',
              'libwild': 'wild', 'linker-layout': 'wild', 'linker-trace': 'wild', 'linker-utils': 'wild',
              'wai-parser': 'wai-parser'}
    packages = []
    for p in sorted(metadata['packages'], key=lambda p: (p['name'], p['version'])):
        ident = p['name'], p['version']
        if ident not in selected:
            continue
        pin = pins[ident]
        if p['source']:
            if pin.get('source') != p['source'] or not p['source'].startswith('registry+'):
                raise ValueError('unexpected package source')
            key = p['name'] + '-' + p['version']
            source = next((WORK / 'cargo-home/registry/cache').glob('*/' + key + '.crate'))
            target = WORK / 'inputs' / (key + '.crate')
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
            add_input(key, target, 'https://static.crates.io/crates/' + p['name'] + '/' + key + '.crate', pin['checksum'])
            manifest_path = key + '/Cargo.toml'
        else:
            key = 'wasmer-source'
            manifest_path = 'wasmer/' + Path(p['manifest_path']).relative_to(WORK / 'wasmer').as_posix()
        if sha(Path(p['manifest_path']).read_bytes()) != sha(contents[key][manifest_path]):
            raise ValueError('metadata source manifest differs from pinned archive')
        prefix = str(Path(manifest_path).parent) + '/'
        names = legal_files(contents[key], prefix)
        notice_key = key
        basis = 'upstream crate legal files, including nested third-party notices'
        if not names and not p['source']:
            names = ['wasmer/LICENSE', 'wasmer/docs/ATTRIBUTIONS.md']
            basis = 'workspace MIT license and upstream attributions; original expression retained'
        if not names:
            supplement = mapped.get(p['name'])
            if p['name'].startswith('cynic'):
                supplement = 'cynic'
            elif p['name'].startswith('wai-') and p['name'] != 'wai-parser':
                supplement = 'wai'
            if supplement:
                notice_key = supplement
                # Root license applies to the crate; avoid unrelated example/vendor licenses.
                names = [n for n in legal_files(contents[supplement]) if n.count('/') == 1]
                basis = 'upstream repository license at recorded archive pin'
        rec = {k: p[k] for k in ('name', 'version', 'source', 'license', 'license_file', 'repository', 'authors')}
        rec.update(input=key, manifest_path=manifest_path, manifest_sha256=sha(contents[key][manifest_path]),
                   role='runtime dependency graph' if ident in runtime else 'proc-macro dependency graph (conservative notice coverage)',
                   notice_basis=basis, notices=[])
        for n in names:
            rec['notices'].append({'input': notice_key, 'path': n, 'sha256': sha(contents[notice_key][n])})
        if not names:
            rec['missing_reason'] = 'No license/notice text in crate; exact upstream license text not established.'
        rec['source_url'] = inputs[key]['url']
        rec['source_sha256'] = inputs[key]['sha256']
        rec['notice_requirements'] = ['Preserve upstream license terms and copyright/attribution text; retain original license expression.']
        if any('notice' in Path(n['path']).name.lower() or 'attribution' in Path(n['path']).name.lower() for n in rec['notices']):
            rec['notice_requirements'].append('Retain bundled upstream NOTICE/attribution documents.')
        if rec['license'] == 'MPL-2.0':
            rec['notice_requirements'].append('MPL source availability: unmodified source at the exact Source URL and SHA256 below.')
        if rec['name'] == 'wasmer-compiler-singlepass':
            rec['notice_requirements'].append('BUSL-1.1: conspicuous license display; non-production and conditional production use terms apply; change license MPL-2.0 after the specified change date.')
        packages.append(rec)
    if [(p['name'], p['version']) for p in packages] != selected:
        raise ValueError('metadata/tree mismatch')
    # These Apache declarations have no separate notice in their full source archive.
    # Preserve the expression, explicitly select Apache where dual-licensed, and ship its terms.
    apache = next(p for p in packages if p['name'] == 'anyhow')
    apache_notice = next(n for n in apache['notices'] if n['path'].endswith('LICENSE-APACHE'))
    for p in packages:
        if p['name'] in ('crc-catalog', 'yaml-edit'):
            key = p['name']; e = supplements[key + '-upstream']
            add_input(key + '-upstream', WORK / (key + '.tar.gz'), e['url'], e['sha256'])
            if legal_files(contents[key + '-upstream']):
                raise ValueError('upstream legal files require explicit review')
            p['notices'] = [dict(apache_notice)]
            p.pop('missing_reason')
            p['notice_basis'] = 'Apache-2.0 distribution terms; Cargo declaration retained; full pinned upstream has no separate legal document. Authors recorded above.'
            p['upstream_no_legal_files_input'] = key + '-upstream'
    for p in packages:
        if (p['name'], p['version']) == ('webc', '12.0.1'):
            p['declaration_acceptance'] = dict(WEBC_DECLARATION)
            if not accepted_declaration(p):
                raise ValueError('webc input differs from accepted declaration')
            p.pop('missing_reason', None)
            p['notice_basis'] = WEBC_DECLARATION['basis']
            p['notice_requirements'] = ['Retain the declared MIT license, exact source/version/hash, and absence of a separate upstream license/copyright file.']
    def extra(name, version, key, names, license):
        return {'name': name, 'version': version, 'repository': None, 'license': license,
                'notices': [{'input': key, 'path': n, 'sha256': sha(contents[key][n])} for n in names]}
    additional = [extra('Wasmer upstream attributions', '7.4.2', 'wasmer', ['LICENSE', 'ATTRIBUTIONS'], 'MIT; embedded upstream licenses retained'),
                  extra('Rust standard library', '1.95.0 (59807616e1fa2540724bfbac14d7976d7e4a3860)', 'rust-1.95.0',
                        ['rustc-1.95.0-aarch64-apple-darwin/rustc/share/doc/rust/COPYRIGHT-library.html'], 'MIT OR Apache-2.0; per-component exceptions in upstream notice')]
    data = assemble(packages + additional, contents)
    with tarfile.open(ROOT / 'build/downloads/wasmer-darwin-arm64.tar.gz') as tar:
        binary = tar.extractfile('bin/wasmer-headless').read()
    import re
    observed = sorted(set((a.decode(), v.decode()) for a, v in re.findall(rb'([A-Za-z0-9_-]+)-([0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9_.+-]*))/src/', binary)))
    doc = {'version': 1, 'complete': not any(p.get('missing_reason') for p in packages), 'runtime_sha256': sha(binary),
           'build': {'package': 'wasmer-cli', 'bin': 'wasmer-headless', 'target': 'aarch64-apple-darwin',
                     'default_features': False, 'features': FEATURES,
                     'source_files': {n: sha((WORK / 'wasmer' / n).read_bytes()) for n in ['Cargo.lock', 'Makefile', '.github/workflows/build.yml', 'lib/cli/Cargo.toml']}},
           'dependency_set_sha256': sha(json.dumps(selected, separators=(',', ':')).encode()),
           'binary_observed_crates': observed,
           'binary_observed_rust_commit': '59807616e1fa2540724bfbac14d7976d7e4a3860',
           'inputs': inputs, 'packages': packages, 'additional_notices': additional,
           'standalone_notices': {
               'licenses/Wasmer-ATTRIBUTIONS.txt': sha(contents['wasmer']['ATTRIBUTIONS']),
               'licenses/Wasmer-Singlepass-BUSL-1.1.txt': sha(contents['wasmer-source']['wasmer/lib/compiler-singlepass/LICENSE'])},
           'bundle_sha256': sha(data), 'missing_notices': [p['name'] for p in packages if p.get('missing_reason')],
           'limitations': ['Cargo graph is a conservative build-input set, not a post-LTO symbol inventory.',
                           'Proc-macro dependencies are recorded separately, not claimed to be linked runtime objects.',
                           'Singlepass has BUSL-1.1 terms, not the workspace MIT license.',
                           'No binary rebuild or full offline Rust closure claimed.']}
    (ROOT / BUNDLE).write_bytes(data)
    (ROOT / INVENTORY).write_text(json.dumps(doc, indent=2) + '\n')
    (ROOT / 'licenses/Wasmer-ATTRIBUTIONS.txt').write_bytes(contents['wasmer']['ATTRIBUTIONS'])
    (ROOT / 'licenses/Wasmer-Singlepass-BUSL-1.1.txt').write_bytes(contents['wasmer-source']['wasmer/lib/compiler-singlepass/LICENSE'])
    print(json.dumps({'packages': len(packages), 'missing': doc['missing_notices'], 'notice_bytes': len(data)}))


if __name__ == '__main__':
    main()
