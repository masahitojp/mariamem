"""Exact-input guest portability series, shared by preparation and release checks."""
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from common import digest


def safe_relative(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('unsafe guest input path: ' + name)
    return name


def descriptor(root, lock):
    root = Path(root)
    value = json.loads((root / 'guest/input.json').read_text())
    # This experiment branch is pinned to one explicitly reviewed target.
    if (value['schema'] != 1 or value['version'] != '13.0.2' or
            value.get('experiment_contract') != 'issue128-target-source-v1' or
            value['source_commit'] != '620a4b5624222048fece7fe1789978ae0675cae2' or
            value['tag_object_sha'] != '308a50778fb4916ddde0d2923feea3d11dcc92c8'):
        raise ValueError('unregistered guest input')
    entries = {e['name']: e for e in lock['inputs']}
    source, recipe = entries[value['source_input']], entries[value['recipe_input']]
    for entry, key in ((source, 'source'), (recipe, 'recipe')):
        if entry['revision'] != value[key + '_source_commit' if key == 'recipe' else 'source_commit']:
            raise ValueError('guest source commit mismatch: ' + key)
        if entry['sha256'] != value[key + '_archive_sha256']:
            raise ValueError('guest source archive mismatch: ' + key)
    for patch in value['patches']:
        name = safe_relative(patch['file'])
        if not name.startswith('guest/patches/') or digest(root / name) != patch['sha256']:
            raise ValueError('guest patch identity mismatch: ' + name)
        text = (root / name).read_text()
        files = re.findall(r'^\+\+\+ b/(.+)$', text, re.M)
        if not files or set(files) != set(patch['before_sha256']) or set(files) != set(patch['after_sha256']):
            raise ValueError('guest patch file inventory differs: ' + name)
        for file in files:
            safe_relative(file)
    overlay = value['source_overlay']
    if (overlay['file'] != 'benchmarks/spikes/issue128-real/inputs/shared-source.patch' or
            digest(root / overlay['file']) != overlay['sha256']):
        raise ValueError('target source overlay identity mismatch')
    files = re.findall(r'^\+\+\+ b/(.+)$', (root / overlay['file']).read_text(), re.M)
    if set(files) != set(overlay['before_sha256']) or set(files) != set(overlay['after_sha256']):
        raise ValueError('target source overlay inventory differs')
    for file in files:
        safe_relative(file)
    native = value.get('native_overlay')
    if (root / 'guest/experimental.patch').exists() != (native is not None):
        raise ValueError('target native overlay presence differs')
    if native is not None:
        if (native['file'] != 'guest/experimental.patch' or
                digest(root / native['file']) != native['sha256']):
            raise ValueError('target native overlay identity mismatch')
        names = re.findall(r'^\+\+\+ b/(.+)$', (root / native['file']).read_text(), re.M)
        if set(names) != set(native['before_sha256']) or set(names) != set(native['after_sha256']):
            raise ValueError('target native overlay inventory differs')
        for name in names:
            safe_relative(name)
    return value


def apply_series(root, source, value):
    records = []
    for patch in value['patches']:
        for name, expected in patch['before_sha256'].items():
            if (digest(source / name) if (source / name).exists() else None) != expected:
                raise ValueError('guest patch preimage differs: ' + name)
        subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i',
                        str(root / patch['file'])], cwd=source, check=True)
        for name, expected in patch['after_sha256'].items():
            if (digest(source / name) if (source / name).exists() else None) != expected:
                raise ValueError('guest patch postimage differs: ' + name)
        records.append(patch)
    return records
