"""Upstream migration pins and fail-closed translation inputs (no compilation)."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / 'benchmarks/spikes/generated-go-integration/translate_guest.py'
spec = importlib.util.spec_from_file_location('upstream_translation', RECIPE)
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


def test_ordered_upstream_identity():
    tools = json.loads((ROOT/'release/generated-go-toolchain.json').read_text())
    translation = json.loads((ROOT/'release/generated-go-translation.json').read_text())
    pins = json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    converter = tools['archives']['converter']
    assert converter['url'] == 'https://codeload.github.com/goccy/wasm2go/tar.gz/' + translation['converter_commit']
    assert converter['sha256'] == translation['converter_archive_sha256'] == recipe.CONVERTER_SHA
    assert pins['converter_commit'] == translation['converter_commit']
    assert list(translation['patches_sha256']) == recipe.PATCHES
    assert recipe.PATCHES == [
        'imported-memory.patch', 'import-function-index.patch', 'relaxed-madd.patch',
        'pure-memory32.patch', 'controlled-thread-traps.patch', 'host-logical-memory.patch',
        'linear-memory-owner.patch', 'helper-bridge.patch', 'export-collision.patch',
        'fd-allocate-preservation.patch', 'zero-bulk-bounds.patch', 'wait-timeout-range.patch',
    ]
    for name, digest in translation['patches_sha256'].items():
        assert hashlib.sha256((ROOT/'benchmarks/spikes/wasm2go'/name).read_bytes()).hexdigest() == digest
    assert pins['guest_sha256'] == translation['guest_sha256']


def test_corrupt_converter_rejected_before_output(tmp_path):
    guest = tmp_path/'guest.wasm'; guest.write_bytes(b'fixture')
    archive = tmp_path/'source.tar.gz'; archive.write_bytes(b'corrupt')
    output = tmp_path/'result'
    result = subprocess.run([sys.executable, str(RECIPE), '--guest', str(guest),
        '--guest-sha256', hashlib.sha256(guest.read_bytes()).hexdigest(),
        '--converter-archive', str(archive), '--output', str(output)], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'input checksum mismatch' in result.stderr
    assert not output.exists()
