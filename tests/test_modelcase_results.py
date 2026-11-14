"""Compacted benchmark statistics remain checkable after raw/build cleanup."""
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1] / 'scripts'))
from layout import BENCHMARKS
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / (BENCHMARKS / 'modelcase/check_results.py')


def invoke(root):
    return subprocess.run([sys.executable, str(CHECKER), '--check', '--results', str(root)],
                          capture_output=True, text=True, timeout=10)


def snapshot(root):
    return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('cohort', ['results', 'shared-read-results'])
def test_compact_check_without_raw_is_read_only(tmp_path, cohort):
    root = tmp_path / 'evidence'
    shutil.copytree(ROOT / (BENCHMARKS / 'modelcase') / cohort, root)
    assert not (root / 'matrix').exists()
    before = snapshot(root)
    result = invoke(root)
    assert result.returncode == 0, result.stderr
    assert snapshot(root) == before


@pytest.mark.parametrize('cohort', ['results', 'shared-read-results'])
def test_resealed_wrong_median_fails_without_writing(tmp_path, cohort):
    root = tmp_path / 'evidence'
    shutil.copytree(ROOT / (BENCHMARKS / 'modelcase') / cohort, root)
    path = root / 'summary.json'
    d = json.loads(path.read_text())
    d['rows'][0]['median_ms'] += 1
    path.write_text(json.dumps(d, indent=2)+'\n')
    manifest = root / 'SHA256SUMS.json'
    hashes = json.loads(manifest.read_text())
    hashes['summary.json'] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(hashes, indent=2)+'\n')
    before = snapshot(root)
    result = invoke(root)
    assert result.returncode != 0
    assert 'recomputed summary.json differs' in result.stderr
    assert snapshot(root) == before


@pytest.mark.parametrize('cohort', ['results', 'shared-read-results'])
def test_input_hash_mismatch_fails(tmp_path, cohort):
    root = tmp_path / 'evidence'
    shutil.copytree(ROOT / (BENCHMARKS / 'modelcase') / cohort, root)
    path = root / 'inputs.json'
    path.write_text(path.read_text()+' ')
    before = snapshot(root)
    result = invoke(root)
    assert result.returncode != 0
    assert 'checksum mismatch: inputs.json' in result.stderr
    assert snapshot(root) == before
