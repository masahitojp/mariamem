"""Separate glue ownership: fail closed on drift, collisions and stale receipts."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from guest_native_glue import install
from guest_input_resolver import resolve_inputs, native_glue_files, _encoded
from guest_preparation_context import resolve, stage_order
from selected_guest import verify_preparation


@pytest.fixture
def selection():
    return resolve(ROOT, '13.2.0', 'native-text')


@pytest.fixture
def source(tmp_path):
    for name in ('wasm', 'libmysqld', 'sql'):
        (tmp_path / name).mkdir()
    return tmp_path


def test_install_exact_glue_bytes_and_modes(selection, source):
    files = install(ROOT, source, selection['guest_input'])
    assert len(files) == 5
    for name, ref in files.items():
        assert (source / name).read_bytes() == (ROOT / ref['file']).read_bytes()
        assert (source / name).stat().st_mode & 0o777 == 0o644
    with pytest.raises(ValueError, match='conflict'):
        install(ROOT, source, selection['guest_input'])


@pytest.mark.parametrize('damage', ['corrupt', 'missing', 'collision', 'symlink', 'parent-link'])
def test_preflight_all_files_before_writing(selection, source, tmp_path, damage):
    guest = copy.deepcopy(selection['guest_input'])
    destination, ref = list(guest['native_glue'].items())[-1]
    data_root = tmp_path / 'inputs'
    for item in guest['native_glue'].values():
        path = data_root / item['file']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / item['file']).read_bytes())
    if damage == 'corrupt': (data_root / ref['file']).write_bytes(b'wrong')
    if damage == 'missing': (data_root / ref['file']).unlink()
    if damage == 'collision': (source / destination).write_bytes(b'upstream addition')
    if damage == 'symlink': (source / destination).symlink_to('missing')
    if damage == 'parent-link':
        (source / 'wasm').rmdir()
        (source / 'wasm').symlink_to(source / 'sql', target_is_directory=True)
    with pytest.raises(ValueError): install(data_root, source, guest)
    first = next(iter(guest['native_glue']))
    assert not (source / first).exists(), 'preflight failure must not leave partial glue'


@pytest.mark.parametrize('damage', ['empty', 'legacy', 'overlap', 'traversal', 'reference'])
def test_invalid_destination_or_profile(selection, damage):
    guest = copy.deepcopy(selection['guest_input'])
    first = next(iter(guest['native_glue']))
    ref = guest['native_glue'][first]
    if damage == 'empty': guest['native_glue'] = {}
    if damage == 'legacy': guest['prepared_profile'] = 'legacy-full'
    if damage == 'overlap':
        target = next(iter(guest['native_overlay']['after_sha256']))
        guest['native_glue'] = {target: ref}
    if damage == 'traversal': guest['native_glue'] = {'../outside': ref}
    if damage == 'reference': ref['file'] = 'guest/elsewhere.cc'
    with pytest.raises(ValueError): native_glue_files(guest)


@pytest.mark.parametrize('damage', ['missing', 'reference-hash', 'bytes'])
def test_resolver_binds_glue_inputs(selection, damage):
    registry = json.loads((ROOT / 'guest/versions/registry.json').read_bytes())
    entry = registry['selections'][selection['selection']]
    desc = json.loads((ROOT / entry['descriptor']['file']).read_bytes())
    ref = next(iter(desc['guest_input']['native_glue'].values()))
    overrides = {}
    if damage == 'missing': del desc['files'][ref['file']]
    if damage == 'reference-hash': ref['sha256'] = '0' * 64
    if damage == 'bytes': overrides[ref['file']] = b'corruption'
    encoded = _encoded(desc)
    overrides[entry['descriptor']['file']] = encoded
    entry['descriptor']['sha256'] = hashlib.sha256(encoded).hexdigest()
    entry['input_sha256'] = hashlib.sha256(_encoded(desc['guest_input'])).hexdigest()
    with pytest.raises(ValueError):
        resolve_inputs(_encoded(registry), '13.2.0', 'native-text',
                       lambda name: overrides[name] if name in overrides else (ROOT / name).read_bytes())


def test_old_producer_receipt_is_not_relabelled(selection):
    old = json.loads((ROOT / 'docs/design/issue134-1320/evidence/prepared-source.json').read_text())
    with pytest.raises(ValueError, match='input identity'):
        verify_preparation(selection, old)


def test_stage_and_historical_selections(selection):
    stages = selection['stages']
    assert stages[stages.index('native_overlay') + 1] == 'native-glue'
    assert stages == stage_order(selection['guest_input'])
    for engine, profile in [('12.3.3', 'legacy-full'), ('13.0.2', 'legacy-full'), ('13.0.2', 'native-text')]:
        historical = resolve(ROOT, engine, profile)
        assert 'native_glue' not in historical['guest_input']
        assert 'native-glue' not in historical['stages']
