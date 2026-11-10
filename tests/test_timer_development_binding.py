"""The experiment accepts one new guest, never a relaxed CRC/ownership ABI."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import generate_runtime as installer
import runtime_crc32c as crc
import runtime_thread_lifetime as threads


@pytest.fixture
def binding(monkeypatch):
    record = json.loads((ROOT/'docs/reviews/wasi-timer-runtime/binding.json').read_text())
    monkeypatch.setattr(crc, 'GUEST_SHA256', record['baseline_guest_sha256'])
    monkeypatch.setattr(threads, 'GUEST_SHA256', record['baseline_guest_sha256'])
    return record


def test_exact_guest_with_identical_bodies(binding):
    installer.select_timer_development_binding(binding)
    assert crc.GUEST_SHA256 == threads.GUEST_SHA256 == binding['guest_sha256']
    text = (ROOT/'tests/fixtures/pinned-crc-validator.go.txt').read_text()
    crc.function(text)
    with pytest.raises(ValueError, match='validator changed'):
        crc.function(text.replace('L36:\n', 'L36:\n return 0\n', 1))


@pytest.mark.parametrize('change', ['data', 'crc', 'thread'])
def test_binding_drift_rejected(binding, monkeypatch, change):
    pins = copy.deepcopy(binding)
    if change == 'data':
        pins['data_sha256'] = '0'*64
    elif change == 'crc':
        monkeypatch.setattr(crc, 'BODY_SHA256', '0'*64)
    else:
        monkeypatch.setattr(threads, 'FUNCTIONS', {})
    with pytest.raises(ValueError, match='differs from reviewed'):
        installer.select_timer_development_binding(pins)
    assert crc.GUEST_SHA256 == threads.GUEST_SHA256 == binding['baseline_guest_sha256']


def test_unknown_guest_is_not_selected(binding):
    installer.select_timer_development_binding(dict(binding, guest_sha256='0'*64))
    assert crc.GUEST_SHA256 == threads.GUEST_SHA256 == binding['baseline_guest_sha256']
    with pytest.raises(ValueError, match='unreviewed'):
        crc.validate_inputs('0'*64, b'')
