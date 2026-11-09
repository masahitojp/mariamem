#!/usr/bin/env python3
"""Assemble a selected native public candidate from verified CI handoff bytes.

No compilation, qualification, publication or canonical overwrite. The producer
checkout is reconstructible from the registered commit, never a private path.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from common import ROOT, digest
from dev_guest import (external_output, inventory, require, source_identity,
                       verify_guest, verify_translation, write)
from guest_preparation_context import resolve
from git_identity import require_commit
from selected_binding import CONTRACT, registered, validate_bodies


def verify_handoff(root, producer, handoff, *, engine, profile):
    selected = resolve(root, engine, profile)
    binding, binding_sha = registered(root, selected['selection'])
    require(binding['upstream_source_commit'] == selected['guest_input']['source_commit'],
            'binding upstream source identity mismatch')
    require_commit(producer, binding['producer_source_commit'])
    producer_identity = source_identity(producer)
    require(producer_identity['commit'] == binding['producer_source_commit'], 'wrong producer checkout')
    require(resolve(producer, engine, profile) == selected, 'host/producer selected inputs differ')
    guest = verify_guest(producer, handoff/'guest', engine=engine, profile=profile)
    translation = handoff/'review/translation'
    raw = verify_translation(producer, translation, guest['guest_sha256'])
    require(guest['source_identity'] == producer_identity and
            guest['source_commit'] == binding['producer_source_commit'] and
            guest['guest_sha256'] == binding['guest_sha256'], 'selected binding producer/guest mismatch')
    for p, key in [('guest/guest.json', 'guest_record_sha256'),
                   ('review/translation/input-manifest.json', 'translation_record_sha256'),
                   ('review/binding-inputs.json', 'binding_input_record_sha256')]:
        require(digest(handoff/p) == binding[key], 'selected handoff receipt mismatch: '+key)
    require(raw['files_sha256'] == binding['translation_files_sha256'], 'selected binding translation mismatch')
    validate_bodies(binding, translation/'module/generated')
    return selected, binding, binding_sha


def verify_installation(record, module, root):
    require(record.get('contract') == CONTRACT and record.get('result') == 'UNQUALIFIED' and
            record.get('release_eligible') is False, 'not selected installation inputs')
    require(record['installer_source_identity'] == source_identity(root), 'stale selected installer source')
    selection, binding, sha = verify_handoff(root, Path(record['producer_directory']),
        Path(record['handoff_directory']), engine=record['engine'], profile=record['profile'])
    require(record['selection'] == selection['selection'] and record['resolved_sha256'] == selection['resolved_sha256'] and
            record['binding_sha256'] == sha and record['guest_sha256'] == binding['guest_sha256'] and
            record['producer_source_commit'] == binding['producer_source_commit'], 'selected installation tuple mismatch')
    require(record['source_inventory'] == inventory(module) and
            record['data_sha256'] == digest(module/'generated/data.bin'), 'selected candidate source/data mismatch')
    validate_bodies(binding, module/'generated')
    return record, binding


def assemble(root, producer, handoff, output, *, engine, profile):
    identity = source_identity(root)
    selected, binding, binding_sha = verify_handoff(root, producer, handoff, engine=engine, profile=profile)
    out = external_output(root, output)
    out.mkdir(parents=True)
    translation = handoff/'review/translation'
    env = dict(os.environ, GOTOOLCHAIN='go1.26.10', GOWORK='off', GOENV='off', GOFLAGS='', GOEXPERIMENT='')
    from build_feedback import run
    run([sys.executable, root/'benchmarks/spikes/generated-go-integration/setup_candidate.py',
         '--source-only', '--source-module', translation/'module', '--guest', handoff/'guest/mariamem.wasm',
         '--input-manifest', translation/'input-manifest.json', '--output', out/'candidate'],
        env=env, check=True, phase='selected:source-adapter')
    module = out/'candidate/module'
    inputs = dict(contract=CONTRACT, result='UNQUALIFIED', release_eligible=False,
        engine=engine, profile=profile, selection=selected['selection'], resolved_sha256=selected['resolved_sha256'],
        installer_source_identity=identity, producer_source_commit=binding['producer_source_commit'],
        producer_directory=str(producer), handoff_directory=str(handoff), binding_sha256=binding_sha,
        guest_sha256=binding['guest_sha256'], data_sha256=digest(module/'generated/data.bin'),
        source_inventory=inventory(module), candidate_files_sha256={
            p.relative_to(module).as_posix():digest(p) for suffix in ('*.go', '*.s') for p in module.rglob(suffix)})
    write(out/'installation-inputs.json', inputs)
    run([sys.executable, root/'scripts/generate_runtime.py', '--source-module', module,
         '--selected-input', out/'installation-inputs.json', '--output', out/'generatedgo'],
        env=env, check=True, phase='selected:installation')
    product = out/'product'
    # Handwritten current source only; old generated runtime cannot fall back.
    for name in identity['files_sha256']:
        if name.startswith('internal/generatedgo/'):
            continue
        target = product/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root/name, target)
    shutil.move(out/'generatedgo', product/'internal/generatedgo')
    shutil.copy2(root/'scripts/runtime_native/factory.go.txt', product/'internal/host/factory.go')
    fixture=(root/'tests/fixtures/native_public/public_test.go.txt').read_text()
    for anchor,value in [('EXPECTED_SELECTED_GUEST_SHA256',binding['guest_sha256']),
                         ('EXPECTED_SELECTED_ENGINE',engine)]:
        require(fixture.count(anchor)==1,'public identity fixture anchor changed')
        fixture=fixture.replace(anchor,value)
    (product/'public_native_test.go').write_text(fixture)
    kind = product/'internal/runtimekind/kind.go'
    canonical = json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256']
    text = kind.read_text()
    anchor = 'const GuestSHA256 = "'+canonical+'"'
    require(text.count(anchor) == 1, 'public guest identity anchor changed')
    kind.write_text(text.replace(anchor, 'const GuestSHA256 = "'+binding['guest_sha256']+'"'))
    # Finite public acceptance guard: positive runs must never use old Serve.
    wire = product/'internal/mysqlwire/wire.go'
    text = wire.read_text()
    require(text.count('func Serve(') == 1, 'legacy Serve tripwire anchor changed')
    pos = text.index('{', text.index('func Serve(')) + 1
    wire.write_text(text[:pos]+'\n panic("legacy wire route tripwire")\n'+text[pos:])
    require(source_identity(root) == identity, 'installer source changed during assembly')
    verify_installation(inputs, module, root)
    write(out/'public-source.json', dict(contract='selected-public-source-v1', result='UNQUALIFIED',
        release_eligible=False, public_acceptance='NOT_RUN', source_commit=identity['commit'],
        producer_source_commit=binding['producer_source_commit'], selection=selected['selection'],
        guest_sha256=binding['guest_sha256'], binding_sha256=binding_sha,
        installation_inputs_sha256=digest(out/'installation-inputs.json'),
        source_inventory=inventory(product)))
    print('Selected public source assembled; runtime acceptance remains required:', product)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--producer-root', type=Path, required=True)
    p.add_argument('--handoff', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--engine', required=True)
    p.add_argument('--profile', required=True)
    a = p.parse_args()
    assemble(ROOT, a.producer_root.resolve(), a.handoff.resolve(), a.output,
             engine=a.engine, profile=a.profile)


if __name__ == '__main__':
    main()
