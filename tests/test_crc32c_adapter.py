"""The CRC binding fails closed when guest semantics or generator output drift."""
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1] / 'scripts'))
from layout import FIXTURES, GENERATED, GENERATED_CODE
import hashlib
import json
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import runtime_crc32c as crc


def raw():
    return (ROOT / (FIXTURES / 'pinned-crc-validator.go.txt')).read_text()


def data():
    table = bytes.fromhex((ROOT / (FIXTURES / 'pinned-crc-table.hex')).read_text())
    return bytes(crc.TABLE_OFFSET) + table


def compact(s):
    return re.sub(r'\s+', '', s)


def test_binding_matches_installed_source_and_preserves_other_checks():
    source = raw()
    assert hashlib.sha256(source.encode()).hexdigest() == crc.BODY_SHA256
    crc.validate_inputs(crc.GUEST_SHA256, data())
    installed = (ROOT / GENERATED / crc.PATH).read_text()
    start = installed.index('func '+crc.FUNCTION+'(')
    end = installed.index('\nfunc ', start + 1)
    adapted = crc.apply(crc.PATH, source)
    assert compact(adapted) == compact(installed[start:end])
    # Every non-CRC block, including the comparison and failure/LSN paths,
    # survives byte for byte. The adapter removes only calculation blocks.
    def blocks(s):
        parts = re.split(r'\n(L\d+):\n', s)
        return {parts[i]: parts[i+1] for i in range(1, len(parts), 2)}
    old, new = blocks(source), blocks(adapted)
    assert set(new) == set(old) - (crc.CRC_BLOCKS - {'L23'})
    assert all(new[k] == v for k, v in old.items() if k not in crc.CRC_BLOCKS)
    assert adapted.count('base.CRC32C(') == 1
    assert 'MARIAMEM_CRC_FAST' not in adapted
    reference = (ROOT/(GENERATED_CODE / 'p4/crc32c_reference_test.go')).read_text()
    assert compact(reference) == compact(crc.reference_source(source))
    helper = (ROOT/(GENERATED_CODE / 'base/crc32c.go')).read_text()
    assert 'os.Getenv' not in helper


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'crc', 'compare', 'lsn', 'table', 'guest', 'truncated'])
def test_unreviewed_binding_rejected(mutation):
    text, memory, guest = raw(), data(), crc.GUEST_SHA256
    if mutation == 'missing':
        text = text.replace(crc.FUNCTION+'(', 'Fn99999(')
    elif mutation == 'duplicate':
        text += '\n' + text
    elif mutation == 'crc':
        text = text.replace('L23:\n', 'L23:\n\tv495 = 0\n', 1)
    elif mutation == 'compare':
        text = text.replace('L36:\n', 'L36:\n\treturn 0\n', 1)
    elif mutation == 'lsn':
        # Change a non-CRC validation block independently of its exact spelling.
        text = text.replace('L81:\n', 'L81:\n\treturn 0\n', 1)
    elif mutation == 'table':
        memory = memory[:-1] + bytes([memory[-1] ^ 1])
    elif mutation == 'guest':
        guest = '0' * 64
    else:
        memory = memory[:-1]
    with pytest.raises(ValueError):
        crc.validate_inputs(guest, memory)
        crc.apply(crc.PATH, text)


def test_unrelated_files_are_untouched():
    assert crc.apply('code/p0/p0_pure.go', 'unrelated') == 'unrelated'


def test_original_table_matches_canonical_data():
    import ast
    source = (ROOT/(GENERATED_CODE / 'generated.go')).read_text()
    literal = source.split('var wasm2goData_data_bin = []byte(', 1)[1].split('\n', 1)[0][:-1]
    memory = ast.literal_eval(literal).encode('latin1')
    pins = json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    crc.validate_inputs(pins['guest_sha256'], memory)
    assert memory[crc.TABLE_OFFSET:crc.TABLE_OFFSET+crc.TABLE_SIZE] == data()[crc.TABLE_OFFSET:]
