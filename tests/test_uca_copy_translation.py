"""Binding inspection is read-only and must not infer runtime acceptance."""
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('uca_copy_translate', ROOT/'tests/uca_copy_translate.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.fixture
def module(tmp_path, monkeypatch):
    folder = tmp_path/'generated/p0'
    folder.mkdir(parents=True)
    thread = 'func Fn1(m *base.Module) {\n\treturn\n}\n'
    crc = 'func Fn2(m *base.Module) {\n\treturn\n}\n'
    (folder/'p0_pure.go').write_text(thread+crc)
    data = b'prefix' + b'crc-table'
    (tmp_path/'generated/data.bin').write_bytes(data)
    monkeypatch.setattr(probe.threads, 'FUNCTIONS', {'code/p0/p0_pure.go': ('Fn1', hashlib.sha256(re.sub(r'\s+', '', thread).encode()).hexdigest())})
    monkeypatch.setattr(probe.crc, 'PATH', 'code/p0/p0_pure.go')
    monkeypatch.setattr(probe.crc, 'FUNCTION', 'Fn2')
    monkeypatch.setattr(probe.crc, 'BODY_SHA256', hashlib.sha256(crc.encode()).hexdigest())
    monkeypatch.setattr(probe.crc, 'TABLE_OFFSET', 6)
    monkeypatch.setattr(probe.crc, 'TABLE_SIZE', 9)
    monkeypatch.setattr(probe.crc, 'TABLE_SHA256', hashlib.sha256(b'crc-table').hexdigest())
    return tmp_path


def test_exact_anchors_do_not_change_existing_guest_binding(module):
    guest = probe.threads.GUEST_SHA256, probe.crc.GUEST_SHA256
    before = {str(p): p.read_bytes() for p in module.rglob('*') if p.is_file()}
    result = probe.inspect_bindings(module)
    assert all(v['exact_match'] for v in result.values())
    assert (probe.threads.GUEST_SHA256, probe.crc.GUEST_SHA256) == guest
    assert {str(p): p.read_bytes() for p in module.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('damage', ['thread', 'crc', 'table', 'offset', 'missing'])
def test_changed_or_missing_anchor_is_reported_without_fuzzy_acceptance(module, damage):
    path = module/'generated/p0/p0_pure.go'
    if damage in ('thread', 'crc'):
        name = 'Fn1' if damage == 'thread' else 'Fn2'
        path.write_text(path.read_text().replace('func '+name, 'func '+name+'Changed'))
    if damage == 'missing':
        path.unlink()
    if damage == 'table':
        (module/'generated/data.bin').write_bytes(b'prefixbroken!!!')
    if damage == 'offset':
        (module/'generated/data.bin').write_bytes(b'new-prefixcrc-table')
    result = probe.inspect_bindings(module)
    assert not all(v['exact_match'] for v in result.values())
