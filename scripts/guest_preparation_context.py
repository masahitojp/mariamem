"""Filesystem adapter for registered preparation inputs, with owned run outputs.

A private input view feeds the existing root-aware helpers. It contains data,
never imported helper code; canonical product files are never rewritten.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from common import digest, fetch
from guest_input_resolver import resolve_inputs, _path


def read_input(root, name):
    """Reject symlinks in every component, including links staying inside root."""
    path = root
    for component in _path(name).split('/'):
        path = path / component
        if path.is_symlink():
            raise ValueError('selected input symlink: ' + name)
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('selected input outside root or missing: ' + name)
    return path.read_bytes()


def stage_order(guest):
    stages = ['extract-and-copy-recipe', 'replace-submodule-placeholders', 'check-pristine']
    if 'source_overlay' in guest:
        stages += ['prepared-uca']
    stages += ['patches', 'source_overlay' if 'source_overlay' in guest else 'canonical-source-patch']
    if 'observation_overlay' in guest:
        stages += ['observation_overlay']
    stages += ['prepared-proof']
    if 'native_overlay' in guest:
        stages += ['native_overlay']
    if 'native_glue' in guest:
        stages += ['native-glue']
    return stages + ['wire-api-and-copied-includes', 'init-hooks', 'auth-hooks', 'auth-header',
                     'routine-schema', 'linker-wrappers', 'vendor-dependencies', 'record-preparation']


def resolve(root, engine, profile):
    root = Path(root).resolve(strict=True)
    result = resolve_inputs(read_input(root, 'guest/versions/registry.json'), engine, profile,
                            lambda name: read_input(root, name))
    if result['stages'] != stage_order(result['guest_input']):
        raise ValueError('registered stage order is not implemented')
    return result


def prepare_selected(root, engine, profile, work_dir, *, archive_cache=None):
    from prepare_guest import prepare
    from prepared_source_patch import inputs as proof_inputs
    root = Path(root).resolve(strict=True)
    result = resolve(root, engine, profile)
    if 'native_overlay' in result['guest_input']:
        branch = subprocess.check_output(['git', '-c', 'safe.directory=' + str(root), 'branch', '--show-current'], cwd=root, text=True).strip()
        if not branch.startswith('experiment/'):
            raise ValueError('native overlay requires an experiment/ branch')
    # Resolve before creating anything; no canonical data is used as scratch.
    work = Path(work_dir).absolute()
    if work.is_symlink():
        raise ValueError('output symlink rejected')
    work = work.resolve()
    if work == root or any(work.is_relative_to(root / name) for name in
                           ('guest', 'release', 'scripts', 'tests', 'docs', '.git')):
        raise ValueError('output overlaps maintained inputs')
    work.mkdir(parents=True, exist_ok=False)
    view = work / 'inputs'
    view.mkdir()
    for name, reference in result['files'].items():
        target = view / name
        target.parent.mkdir(parents=True, exist_ok=True)
        # Recheck the bytes used, not merely those seen at resolution time.
        data = read_input(root, reference['file'])
        if hashlib.sha256(data).hexdigest() != reference['sha256']:
            raise ValueError('input changed during preparation: ' + name)
        target.write_bytes(data)
    for name, value in (('guest/input.json', result['guest_input']),
                        ('release/inputs.lock.json', result['effective_lock'])):
        target = view / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2) + '\n')
    proof_inputs(view)  # Full corrected profile/TIME/unchanged-file contract.
    (work / 'resolved-input.json').write_text(json.dumps(result, indent=2) + '\n')
    downloads = work / 'downloads' if archive_cache is None else Path(archive_cache).resolve()
    if downloads == work or downloads.is_relative_to(view):
        raise ValueError('download cache overlaps input view')
    manifest = prepare(view, result['effective_lock'], work,
                       lambda name: fetch(name, lock=result['effective_lock'], downloads=downloads),
                       selected=result['guest_input'])
    manifest.update(resolved_input_sha256=digest(work / 'resolved-input.json'),
                    selection=result['selection'], experimental=('native_overlay' in result['guest_input']))
    (work / 'prepared-source.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest
