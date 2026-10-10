#!/usr/bin/env python3
"""Regenerate canonical generated Go in a disposable tree and compare every byte."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from common import ROOT, digest
from build_generated_guest import download
from build_feedback import go_environment, run as observed_run


def inventory(root):
    return {p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--guest-dir',type=Path,default=ROOT/'build/generated-release')
    p.add_argument('--output',type=Path,default=ROOT/'build/release-regeneration')
    a=p.parse_args(); guest=a.guest_dir.resolve(); out=a.output.resolve()
    pins=json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    record=json.loads((guest/'guest.json').read_text())
    if digest(guest/'mariamem.wasm') != pins['guest_sha256'] or record['guest_sha256'] != pins['guest_sha256']:
        p.error('unaccepted guest identity')
    tools=json.loads((ROOT/'release/generated-go-toolchain.json').read_text())
    converter=download(tools['archives']['converter'],ROOT/'build/downloads')
    env=go_environment(dict(os.environ,GOTOOLCHAIN='go1.26.8',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT=''))
    out.mkdir(parents=True,exist_ok=False)
    spike=ROOT/'benchmarks/spikes/generated-go-integration'
    commands=[
      [spike/'translate_guest.py','--guest',guest/'mariamem.wasm','--guest-sha256',pins['guest_sha256'],
       '--converter-archive',converter,'--output',out/'translation'],
      [ROOT/'benchmarks/spikes/memory-candidate/check_fixture.py','--converter',out/'translation/wasm2go',
       '--output',out/'memory32-regression'],
      [spike/'setup_candidate.py','--source-only','--source-module',out/'translation/module',
       '--guest',guest/'mariamem.wasm','--input-manifest',ROOT/'release/generated-go-translation.json','--output',out/'candidate'],
      [ROOT/'scripts/generate_runtime.py','--source-module',out/'candidate/module','--output',out/'generatedgo']]
    for command, phase, outputs in zip(commands,
            ['regenerate:translation', 'regenerate:memory32-fixture',
             'regenerate:source-adapter', 'regenerate:installation'],
            [[out/'translation/input-manifest.json'], [], [], [out/'generatedgo/provenance.json']]):
        observed_run([sys.executable,*map(str,command)],cwd=ROOT,env=env,check=True,
                     phase=phase, inputs=[guest/'mariamem.wasm', ROOT/'release/generated-go-inputs.json'],
                     outputs=outputs)
    if inventory(out/'generatedgo') != inventory(ROOT/'internal/generatedgo'):
        raise ValueError('regenerated output differs from committed source (including ownership glue)')
    proof={'contract':'generated-go-v1','source_commit':record['source_commit'],
           'guest_sha256':pins['guest_sha256'],'generated_inventory':inventory(out/'generatedgo'),
           'raw_translation':json.loads((out/'translation/input-manifest.json').read_text()),
           'input_manifest_sha256':digest(ROOT/'release/generated-go-inputs.json'),
           'toolchain_pins_sha256':digest(ROOT/'release/generated-go-toolchain.json'),
           'provenance_sha256':digest(ROOT/'internal/generatedgo/provenance.json'),'result':'PASS'}
    (guest/'regeneration.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
    print('PASS: independently regenerated source equals canonical checked-in source')

if __name__ == '__main__': main()
