"""Exercise the exact experimental probe without starting a guest."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('host_volume_read', ROOT / 'benchmarks/host_volume_read.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.fixture
def binary(tmp_path):
    if not shutil.which('cc'):
        pytest.skip('native probe needs a C compiler')
    source = tmp_path / 'probe.c'
    source.write_text(probe.probe_source())
    target = tmp_path / 'probe'
    subprocess.run(['cc', '-O2', '-std=gnu11', '-Wall', '-Wextra', str(source), '-o', str(target)], check=True)
    return target


def fixture(root):
    data = root / 'data'
    (data / 'nested').mkdir(parents=True)
    (data / 'empty').write_bytes(b'')
    (data / 'nested/payload').write_bytes(bytes(range(256)) * 256 + b'end')
    entries = {'.': {'kind': 'directory'}, 'nested': {'kind': 'directory'}}
    for p in data.rglob('*'):
        if p.is_file():
            entries[p.relative_to(data).as_posix()] = {'kind': 'file', 'bytes': p.stat().st_size, 'sha256': probe.digest(p)}
    (root / 'manifest.json').write_text(json.dumps({'version': 1, 'entries': entries}))
    return probe.snapshot_identity(root)


def test_same_inventory_and_content_without_destination(binary, tmp_path):
    snapshot = tmp_path / 'snapshot'
    identity = fixture(snapshot)
    checksums = None
    for mode in ['stdio', 'direct']:
        result = subprocess.run([str(binary), str(snapshot / 'data'), mode], capture_output=True, text=True, check=True)
        row = probe.read_report(result.stdout, identity, checksums, mode)
        assert row['total_bytes'] == 65539
        assert row['total_read_calls'] == 4  # two payload reads + EOF, empty EOF
        assert row['read_wall_ns'] >= 0
        checksums = {name: item['checksum_fnv1a64'] for name, item in row['files'].items()}
        assert probe.snapshot_identity(snapshot)['files'] == identity['files']
    with pytest.raises(ValueError, match='mode mismatch'):
        probe.read_report(result.stdout, identity, expected_mode='stdio')
    checksums['empty'] = 'invalid'
    with pytest.raises(ValueError, match='checksum'):
        probe.read_report(result.stdout, identity, checksums)


def test_missing_inventory_and_corruption_fail_closed(tmp_path):
    identity = fixture(tmp_path / 'snapshot')
    with pytest.raises(ValueError, match='inventory'):
        probe.read_report(json.dumps({'completed': True, 'destination_writes': 0, 'chunk_bytes': 65536}), identity)
    (tmp_path / 'snapshot/data/nested/payload').write_bytes(b'bad')
    with pytest.raises(ValueError, match='integrity'):
        probe.snapshot_identity(tmp_path / 'snapshot')


def test_manifest_root_is_required_and_validated(tmp_path):
    snapshot = tmp_path / 'snapshot'
    fixture(snapshot)
    path = snapshot / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['entries']['.'] = {'kind': 'file', 'bytes': 0, 'sha256': 'invalid'}
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='entry type'):
        probe.snapshot_identity(snapshot)
    del manifest['entries']['.']
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='inventory mismatch'):
        probe.snapshot_identity(snapshot)


def test_symlink_and_unknown_mode_rejected(binary, tmp_path):
    fixture(tmp_path / 'snapshot')
    (tmp_path / 'snapshot/data/link').symlink_to('empty')
    result = subprocess.run([str(binary), str(tmp_path / 'snapshot/data'), 'stdio'], capture_output=True)
    assert result.returncode != 0
    with pytest.raises(ValueError, match='unsafe'):
        probe.snapshot_identity(tmp_path / 'snapshot')
    assert subprocess.run([str(binary), str(tmp_path), 'unknown'], capture_output=True).returncode != 0
