"""Exact reviewed worker bindings for isolated selected guests.

Registration is data, not a version branch or fuzzy matcher. Canonical defaults
and release ledgers are deliberately outside this contract.
"""
import hashlib
import json
import re
from pathlib import Path

from common import digest
from dev_guest import require
from runtime_thread_lifetime import function, apply as canonical_apply

CONTRACT = 'selected-runtime-installation-v1'
ABI = {'start_args.pthread': 16, 'pthread.map_base': 40, 'pthread.map_size': 44}


def registered(root, selection):
    registry = json.loads((root/'guest/bindings/registry.json').read_text())
    require(selection in registry, 'selected worker binding is not registered')
    ref = registry[selection]
    path = root/ref['file']
    require(path.resolve().is_relative_to((root/'guest/bindings').resolve()) and
            not path.is_symlink() and digest(path) == ref['sha256'], 'binding registry identity mismatch')
    record = json.loads(path.read_text())
    require(record.get('schema') == 'selected-worker-binding-v1' and
            record.get('release_eligible') is False and record['selection'] == selection and
            record['ABI_offsets'] == ABI, 'selected worker binding contract/ABI mismatch')
    items = record['functions']
    require(len(items) == 3 and {v['role'] for v in items.values()} == {'free', 'yield', 'entry'} and
            all(re.fullmatch(r'code/p\d+/p\d+_pure\.go', k) and
                re.fullmatch(r'Fn\d+', v['function']) and
                re.fullmatch(r'[0-9a-f]{64}', v['normalized_sha256']) for k,v in items.items()),
            'selected worker binding function inventory mismatch')
    return record, ref['sha256']


def body_hash(text):
    return hashlib.sha256(re.sub(r'\s+', '', text).encode()).hexdigest()


def validate_bodies(binding, generated):
    for path, item in binding['functions'].items():
        body = function((generated/path.removeprefix('code/')).read_text(), item['function'])
        require(body_hash(body) == item['normalized_sha256'], 'selected worker body changed: '+item['role'])
    tls = re.findall(r'm.G2 = int32\((\d+)\)', (generated/'generated.go').read_text())
    require(tls and set(tls) == {str(binding['tls_init_bytes'])}, 'selected TLS initialization changed')
    table = []
    for p in generated.glob('p*/*.go'):
        table.extend(re.findall(r'm.T0\['+str(binding['noop_table_index'])+r'\] = (Fn\d+)\n', p.read_text()))
    require(table == [binding['noop_function']], 'selected no-op table target changed')
    noop = function((generated/binding['noop_file'].removeprefix('code/')).read_text(), binding['noop_function'])
    require(re.sub(r'\s+', '', noop) == 'func'+binding['noop_function']+'(m*base.Module,l0int32){return}',
            'selected entry no-op body changed')


def apply(binding, name, text):
    if name == 'code/base/base.go':
        return canonical_apply(name, text)
    item = binding['functions'].get(name)
    if item is None:
        return text
    require(body_hash(function(text, item['function'])) == item['normalized_sha256'],
            'selected worker body changed during installation')
    if item['role'] == 'free':
        anchor = 'func '+item['function']+'(m *base.Module, l0 int32) {\n'
        require(text.count(anchor) == 1, 'selected allocator signature changed')
        return text.replace(anchor, anchor+'\tif base.DeferThreadAllocationFree(m, l0) { return }\n', 1)
    return text


def wrapper(binding):
    path, item = next((p,v) for p,v in binding['functions'].items() if v['role'] == 'free')
    part = path.split('/')[1]
    prefix = 'github.com/masahitojp/mariamem/internal/generatedgo/code/'
    return ('// Selected exact-guest allocation binding; UNQUALIFIED.\npackage generatedgo\n'
            'import ("'+prefix+'base"; "'+prefix+part+'")\n'
            'func installGuestThreadLifetime(m *base.Module) {\n'
            '\tbase.InstallThreadLifetime(m, '+part+'.'+item['function']+')\n}\n')
