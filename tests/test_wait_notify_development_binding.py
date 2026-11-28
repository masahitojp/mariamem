"""Development-only exact binding selection must preserve fail-closed behavior."""
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import runtime_thread_lifetime as thread
import runtime_crc32c as crc


@pytest.fixture
def installer(monkeypatch):
    for module, names in ((thread, ('GUEST_SHA256', 'FUNCTIONS')),
                          (crc, ('GUEST_SHA256', 'FUNCTION', 'BODY_SHA256',
                                 'TABLE_OFFSET', 'TABLE_SHA256'))):
        for name in names:
            monkeypatch.setattr(module, name, getattr(module, name))
    spec = importlib.util.spec_from_file_location('wait_installer', ROOT/'scripts/generate_runtime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unknown_guest_keeps_canonical_guards(installer):
    old = thread.GUEST_SHA256
    assert installer.development_wait_binding({'guest_sha256': '0'*64}) is None
    assert thread.GUEST_SHA256 == crc.GUEST_SHA256 == old
    with pytest.raises(ValueError, match='unreviewed'):
        thread.validate_inputs('0'*64, {})


def test_exact_profile_keeps_function_and_table_guards(installer):
    candidate = 'e6d0570841d79b82cfee1a87070080febeb08da6dba1727c5341e53ae6463c9b'
    profile = installer.development_wait_binding({'guest_sha256': candidate})
    required = {'generated/base/base.go', *('generated/'+p.removeprefix('code/') for p in thread.FUNCTIONS)}
    thread.validate_inputs(candidate, required)
    for missing in required:
        with pytest.raises(ValueError, match='unreviewed'):
            thread.validate_inputs(candidate, required-{missing})
    for name, (fn, _) in thread.FUNCTIONS.items():
        with pytest.raises(ValueError, match='function changed'):
            thread.apply(name, 'func '+fn+'() {}\n')
    with pytest.raises(ValueError, match='unreviewed'):
        crc.validate_inputs(candidate, b'')
    with pytest.raises(ValueError, match='validator changed'):
        crc.function('func '+profile['crc_function']+'() {}\n')


def test_profile_mutation_rejected(installer, monkeypatch, tmp_path):
    fixture = tmp_path/'tests/fixtures/wait-notify-binding.json'
    fixture.parent.mkdir(parents=True)
    fixture.write_text('{}')
    monkeypatch.setattr(installer, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='profile changed'):
        installer.development_wait_binding({'guest_sha256': 'e6d0570841d79b82cfee1a87070080febeb08da6dba1727c5341e53ae6463c9b'})
