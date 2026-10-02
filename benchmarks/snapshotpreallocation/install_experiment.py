#!/usr/bin/env python3
"""Reconstruct Lane B's direct-link diagnostic from explicit regenerated inputs.

Never overwrites the checkout: new output must be outside it. No generated
function/address edits, no relaxed digest gates, no executable provisioning.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BASE = '6940bf1ac3010a020c8a67cd366d9e26c42c4974'
OLD = 'example.com/mariamem-spike/generated'
NEW = 'github.com/masahitojp/mariamem/internal/generatedgo/code'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def install_function_tree(source, destination, data):
    # Package shards contain the actual generated guest functions. Rebuild all
    # non-base files; root-only copying can silently retain old function bodies.
    for child in destination.iterdir():
        if child.name == 'base': continue
        if child.is_dir(): shutil.rmtree(child)
        else: child.unlink()
    transformed = []
    for file in source.rglob('*.go'):
        name = file.relative_to(source)
        if name.parts[0] == 'base': continue
        text = file.read_text().replace(OLD, NEW)
        if name.as_posix() == 'generated.go':
            text = text.replace('\t_ "embed"\n','')
            marker = '//go:embed data.bin\nvar wasm2goData_data_bin []byte'
            if text.count(marker) != 1: raise ValueError('generated data marker changed')
            text = text.replace(marker, 'var wasm2goData_data_bin = []byte("'+''.join('\\x%02x'%b for b in data)+'")')
        out = destination/name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        transformed.append(out)
    expected = {str(f.relative_to(source)) for f in source.rglob('*.go') if f.relative_to(source).parts[0] != 'base'}
    actual = {str(f.relative_to(destination)) for f in destination.rglob('*') if f.is_file() and f.relative_to(destination).parts[0] != 'base'}
    if actual != expected: raise ValueError('incomplete transformed function tree')
    return transformed

def write_runtime_provenance(target, translated, manifest):
    runtime = target/'internal/generatedgo'
    hand = {'runtime_instance.go','code/base/runtime_cleanup.go'}
    files = {str(f.relative_to(runtime)):sha(f) for f in runtime.rglob('*')
             if f.is_file() and f.name != 'provenance.json' and str(f.relative_to(runtime)) not in hand}
    record = {'guest_sha256':manifest['guest_sha256'],
              'input_manifest_sha256':sha(translated/'input-manifest.json'),
              'files_sha256':files,
              'scope':'experimental direct-link source inventory, not canonical release/platform-image provenance'}
    (runtime/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--translation', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    target, translated = a.output.resolve(), a.translation.resolve()
    if target.exists() or target.is_relative_to(ROOT): p.error('fresh external output required')
    manifest = json.loads((translated/'input-manifest.json').read_text())
    source = translated/'module/generated'
    inventory = {str(f.relative_to(source)):sha(f) for f in source.rglob('*') if f.is_file()}
    if inventory != manifest['files_sha256']: p.error('translation inventory mismatch')
    if sha(translated/'guest.wasm') != manifest['guest_sha256']: p.error('guest digest mismatch')
    original = json.loads((ROOT/'benchmarks/spikes/generated-go-integration/llvm23-generated-source.json').read_text())
    for name,digest in original['files_sha256'].items():
        if name.startswith('base/') and inventory.get(name) != digest:
            p.error('generator/runtime changed beyond guest functions: '+name)
    target.mkdir(parents=True)
    archive = subprocess.check_output(['git','archive',BASE],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as t: t.extractall(target,filter='data')
    destination = target/'internal/generatedgo/code'
    data = (source/'data.bin').read_bytes()
    transformed = install_function_tree(source, destination, data)
    old_sha = json.loads((target/'release/generated-go-inputs.json').read_text())['guest_sha256']
    new_sha = manifest['guest_sha256']
    bindings = ['internal/generatedgo/entry.go','internal/generatedgo/guest_identity.go','internal/runtimekind/kind.go']
    for name in bindings:
        file=target/name
        text=file.read_text()
        if text.count(old_sha)!=1: p.error('guest identity binding changed: '+name)
        file.write_text(text.replace(old_sha,new_sha))
    shutil.copytree(ROOT/'benchmarks/snapshotpreallocation',target/'benchmarks/snapshotpreallocation')
    env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOWORK='off')
    subprocess.run(['gofmt','-w',*map(str,transformed)],env=env,check=True)
    write_runtime_provenance(target, translated, manifest)
    generated_inventory = {str(f.relative_to(target/'internal/generatedgo')):sha(f) for f in (target/'internal/generatedgo').rglob('*') if f.is_file()}
    record={'base_sha':BASE,'recipe_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'guest_sha256':new_sha,'translation_manifest_sha256':sha(translated/'input-manifest.json'),'unchanged_base_inventory_verified':True,'identity_binding_files':bindings,'diagnostic_generated_inventory':generated_inventory,'scope':'external experiment; committed canonical generated source, executable image pins and release identity unchanged; not a release candidate'}
    (target/'experiment-provenance.json').write_text(json.dumps(record,indent=2)+'\n')
    print(target)
if __name__=='__main__': main()
