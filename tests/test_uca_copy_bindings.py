"""Negative guards for the one-guest experimental runtime binding."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import uca_copy_bindings as b

ROOT = Path(__file__).resolve().parents[1]


def test_binding_is_process_local_and_exact():
    before = {name: (ROOT/'scripts'/f'{name}.py').read_bytes() for name in b.ADAPTERS}
    modules = b.load(ROOT)
    thread = modules['runtime_thread_lifetime']
    names = {'generated/base/base.go', *('generated/'+p.removeprefix('code/') for p in b.FUNCTIONS)}
    thread.validate_inputs(b.GUEST, names)
    with pytest.raises(ValueError):
        thread.validate_inputs(b.CANONICAL, names)
    with pytest.raises(ValueError):
        thread.validate_inputs(b.GUEST, set())
    assert all((ROOT/'scripts'/f'{n}.py').read_bytes() == data for n, data in before.items())
    assert b.load(ROOT)['runtime_crc32c'].TABLE_OFFSET == 7930560


def test_modified_adapter_rejected(tmp_path):
    (tmp_path/'scripts').mkdir()
    for name in b.ADAPTERS:
        (tmp_path/'scripts'/f'{name}.py').write_bytes((ROOT/'scripts'/f'{name}.py').read_bytes()+b'\n')
    with pytest.raises(ValueError, match='unreviewed adapter'):
        b.load(tmp_path)


def test_changed_function_and_table_fail_closed():
    modules = b.load(ROOT)
    t = modules['runtime_thread_lifetime']
    with pytest.raises(ValueError, match='function changed'):
        t.apply('code/p3/p3_pure.go', 'func Fn153(m *base.Module, l0 int32) {\n}\n')
    c = modules['runtime_crc32c']
    with pytest.raises(ValueError, match='validator changed'):
        c.function('func Fn18145() {}\n')
    with pytest.raises(ValueError, match='table binding'):
        c.validate_inputs(b.GUEST, b'')
