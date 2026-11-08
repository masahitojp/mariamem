#!/usr/bin/env python3
"""Derive complete target patch images from the three already reviewed repairs.

Run once for this experiment; the resulting pins, not dynamic hash acceptance,
are consumed by fresh preparation. No runtime expectation is generated here.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import common
from common import digest, extract, fetch
from uca_prepared import prepare as prepare_uca
from prepared_source_patch import check_functions

scratch = ROOT / 'build/issue128-real/temp/pin-source'
scratch.mkdir(parents=True, exist_ok=False)
pin = json.loads((ROOT / 'guest/input.json').read_text())
assert pin['source_commit'] == '620a4b5624222048fece7fe1789978ae0675cae2'
downloads = ROOT / 'build/downloads'
# All downloads are placed inside owned storage, exposed at build/downloads by
# a task-owned symlink for the existing acquisition helper.
records = {}
for name in ('mariadb', 'lite4mariadb', 'libmariadb', 'wolfssl', 'pcre2', 'libfmt'):
    path = fetch(name)
    records[name] = {'sha256': digest(path), 'bytes': path.stat().st_size}
    if name not in ('pcre2', 'libfmt'):
        extract(path, scratch / name)
recipe = next((scratch / 'lite4mariadb').iterdir())
source = next((scratch / 'mariadb').iterdir())
for name, expected in pin['recipe_files_sha256'].items():
    assert digest(recipe / name) == expected
    (source / name).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(recipe / name, source / name)
for name, relative in [('libmariadb', 'libmariadb'), ('wolfssl', 'extra/wolfssl/wolfssl')]:
    target = source / relative
    target.rmdir()
    shutil.move(str(next((scratch / name).iterdir())), target)
prepare_uca(ROOT, source)


def apply(path):
    names = sorted(set(re.findall(r'^\+\+\+ b/(.+)$', path.read_text(), re.M)))
    before = {n: digest(source / n) if (source / n).exists() else None for n in names}
    subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(path)],
                   cwd=source, check=True)
    after = {n: digest(source / n) for n in names}
    return {'file': str(path.relative_to(ROOT)), 'sha256': digest(path),
            'before_sha256': before, 'after_sha256': after}


patches = []
for old in pin['patches']:
    relative = old['file'].replace('12.3.3-', '13.0.2-')
    patches.append(apply(ROOT / relative))
pin['patches'] = patches
pin['source_overlay'] = apply(ROOT / 'benchmarks/spikes/issue128-real/inputs/shared-source.patch')
# Both published legacy and native use this prepared UCA base for comparison.
pin['experiment_contract'] = 'issue128-target-source-v1'
(ROOT / 'guest/input.json').write_text(json.dumps(pin, indent=2) + '\n')
prepared = json.loads((ROOT / 'guest/prepared_source_patch.json').read_text())
entry = next(p for p in patches if p['file'].endswith('-prepared.patch'))
prepared.update(source_commit=pin['source_commit'], patch_file=entry['file'],
                patch_sha256=entry['sha256'])
for item in prepared['files']:
    item['before_sha256'] = entry['before_sha256'][item['file']]
    item['after_sha256'] = entry['after_sha256'][item['file']]
(ROOT / 'guest/prepared_source_patch.json').write_text(json.dumps(prepared, indent=2) + '\n')
check_functions(source, ROOT, 'after')
output = ROOT / 'benchmarks/spikes/issue128-real/evidence/dependency-acquisition.json'
output.write_text(json.dumps(records, indent=2) + '\n')
print('Pinned exact complete target images; original function expectations pass')
