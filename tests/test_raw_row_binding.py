"""Candidate selection retains canonical guards and rejects changed full bodies."""
import hashlib
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import generate_runtime as installer
import runtime_thread_lifetime as threads
import runtime_crc32c as crc

PROFILE = ROOT/'docs/reviews/prepared-row-adapter/binding'


@pytest.fixture
def selected(monkeypatch):
    for module, names in ((threads, ('GUEST_SHA256', 'FUNCTIONS')),
                          (crc, ('GUEST_SHA256', 'FUNCTION', 'PATH', 'BODY_SHA256', 'TABLE_OFFSET'))):
        for name in names:
            monkeypatch.setattr(module, name, getattr(module, name))
    record = json.loads((PROFILE/'identity.json').read_text())
    installer.select_development_binding(record)
    return record


def test_unknown_guest_keeps_canonical_binding():
    before = (threads.GUEST_SHA256, crc.GUEST_SHA256)
    installer.select_development_binding({'guest_sha256':'0'*64})
    assert before == (threads.GUEST_SHA256, crc.GUEST_SHA256)


def test_wrong_candidate_data_rejected():
    record = json.loads((PROFILE/'identity.json').read_text())
    record['data_sha256'] = '0'*64
    with pytest.raises(ValueError, match='data identity'):
        installer.select_development_binding(record)


def test_full_worker_preimages_and_mutations(selected):
    files = {'generated/base/base.go', *('generated/'+p.removeprefix('code/') for p in threads.FUNCTIONS)}
    threads.validate_inputs(selected['guest_sha256'], files)
    with pytest.raises(ValueError):
        threads.validate_inputs('0'*64, files)
    for name, (fn, _) in threads.FUNCTIONS.items():
        source = (PROFILE/(fn+'.txt')).read_text()
        threads.apply(name, source)
        with pytest.raises(ValueError):
            threads.apply(name, source.replace('mBase := m.M', 'mBase := unsafe.Pointer(nil)', 1))


def test_crc_full_body_table_and_non_crc_mutation(selected):
    source = (PROFILE/'crc.txt').read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == crc.BODY_SHA256
    adapted = crc.apply(crc.PATH, source)
    assert adapted.count('base.CRC32C(') == 1
    with pytest.raises(ValueError):
        crc.apply(crc.PATH, source.replace('L36:\n', 'L36:\n\treturn 0\n', 1))
    table = bytes.fromhex((ROOT/'tests/fixtures/pinned-crc-table.hex').read_text())
    memory = bytes(crc.TABLE_OFFSET)+table
    crc.validate_inputs(selected['guest_sha256'], memory)
    with pytest.raises(ValueError):
        crc.validate_inputs(selected['guest_sha256'], memory[:-1])
    with pytest.raises(ValueError):
        crc.validate_inputs('0'*64, memory)
