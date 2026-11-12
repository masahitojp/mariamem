"""Negative guards for the one-guest experimental runtime binding."""
import json
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


def test_crc_fixture_relocation_preserves_all_oracles():
    path = ROOT/'internal/generatedgo/code/p4/crc32c_test.go'
    original = path.read_text()
    updated = b.crc_test_source(original)
    # Restore only the two setup literals: every other byte must agree,
    # including the independent expected rejection of corrupt payloads.
    restored = updated
    for before, after in b.CRC_TEST_RELOCATIONS.items():
        assert updated.count(after) == 1 and before not in updated
        restored = restored.replace(after, before)
    assert restored == original
    assert 'mutation != "valid" && old == 0' in updated
    assert path.read_text() == original
    assert 8388608 + b.CRC_OFFSET == 16319168
    pairs = json.loads((ROOT/'docs/reviews/issue154-uca-data/ci-43105781665.json').read_text())['local_source_comparison']['crc']['integer_changes']
    assert [26865072, 27614704] in pairs


def test_changed_crc_fixture_oracle_rejected():
    original = (ROOT/'internal/generatedgo/code/p4/crc32c_test.go').read_text()
    with pytest.raises(ValueError, match='unreviewed original CRC test fixture'):
        b.crc_test_source(original.replace('mutation != "valid" && old == 0', 'false'))
    with pytest.raises(ValueError, match='unreviewed original CRC test fixture'):
        b.crc_test_source(b.crc_test_source(original))
