"""Saved benchmark analysis survives cleanup and never mutates evidence in check mode."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'benchmarks/v060-latency-evidence'
ANALYZER = EVIDENCE / 'analyze.py'


def invoke(root, *args):
    return subprocess.run([sys.executable, str(ANALYZER), '--evidence-dir', str(root), *args],
                          capture_output=True, text=True, timeout=10)


def snapshot(root):
    return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


def refresh_hash(root, name):
    path = root / 'SHA256SUMS.json'
    hashes = json.loads(path.read_text())
    hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    path.write_text(json.dumps(hashes, indent=2)+'\n')


def test_check_after_cleanup_is_read_only_and_default_only_writes_summaries(tmp_path):
    root = tmp_path / 'evidence'
    shutil.copytree(EVIDENCE, root)
    assert not (tmp_path / 'temp').exists()
    before = snapshot(root)
    result = invoke(root, '--check')
    assert result.returncode == 0, result.stderr
    assert snapshot(root) == before
    target = tmp_path / 'summary'
    result = invoke(root, '--output-dir', str(target))
    assert result.returncode == 0, result.stderr
    assert {p.name for p in target.iterdir()} == {'summary.json', 'summary.csv'}
    for name in ('summary.json', 'summary.csv'):
        assert (target / name).read_bytes() == (root / name).read_bytes()
    assert snapshot(root) == before


@pytest.mark.parametrize('name', ['summary.json', 'summary.csv', 'samples.json'])
def test_check_rejects_resealed_wrong_statistics_without_writing(tmp_path, name):
    root = tmp_path / 'evidence'
    shutil.copytree(EVIDENCE, root)
    path = root / name
    if name == 'summary.json':
        data = json.loads(path.read_text())
        data['rows'][0]['candidate_ms'] += 1
        path.write_text(json.dumps(data, indent=2)+'\n')
    elif name == 'summary.csv':
        path.write_text(path.read_text().replace('213.497669', '999.497669'))
    else:
        data = json.loads(path.read_text())
        data['go']['light-fresh']['baseline'][0]['suite_ms'] = 999
        path.write_text(json.dumps(data)+'\n')
    refresh_hash(root, name)  # A self-consistent manifest is not proof of correct statistics.
    before = snapshot(root)
    result = invoke(root, '--check')
    assert result.returncode != 0
    assert 'recomputed' in result.stderr
    assert snapshot(root) == before


def test_check_rejects_identity_tampering(tmp_path):
    root = tmp_path / 'evidence'
    shutil.copytree(EVIDENCE, root)
    path = root / 'inputs.json'
    path.write_text(path.read_text()+' ')
    before = snapshot(root)
    result = invoke(root, '--check')
    assert result.returncode != 0
    assert 'checksum mismatch: inputs.json' in result.stderr
    assert snapshot(root) == before
