"""Safety boundaries for the development-only cleanup allowlist."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('development_cleanup', ROOT/'scripts/clean_development.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


def test_canonical_and_cache_paths_never_selected(tmp_path):
    for name in ['docs', 'guest', 'benchmarks/spikes', 'build/downloads', 'build/tools', 'build/generated-go-integration/llvm23-candidate']:
        (tmp_path/name).mkdir(parents=True, exist_ok=True)
    assert cleanup.targets(tmp_path) == []


def test_symlink_target_refused(tmp_path):
    target = tmp_path/'tests/runs'
    target.parent.mkdir()
    protected = tmp_path/'source'
    protected.mkdir()
    target.symlink_to(protected, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        cleanup.targets(tmp_path)


def test_symlink_ancestor_refused(tmp_path):
    protected = tmp_path/'source'
    (protected/'runs').mkdir(parents=True)
    (tmp_path/'tests').symlink_to(protected, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        cleanup.targets(tmp_path)


def test_evidence_preserves_small_results_not_build_sources(tmp_path):
    target = tmp_path/'tests/runs'
    (target/'source').mkdir(parents=True)
    (target/'summary.json').write_text('{"passed":true}')
    (target/'source/irrelevant.json').write_text('{}')
    (target/'image.bin').write_bytes(b'raw')
    destination = tmp_path/'evidence'
    records = cleanup.export_evidence(tmp_path, [target], destination)
    assert [r['path'] for r in records] == ['tests/runs/summary.json']
    assert (destination/'tests/runs/summary.json').read_text() == '{"passed":true}'
    assert (target/'image.bin').exists()  # Export is non-destructive.


def test_evidence_cannot_be_written_under_deleted_tree(tmp_path):
    target = tmp_path/'tests/runs'
    target.mkdir(parents=True)
    with pytest.raises(ValueError, match='inside'):
        cleanup.export_evidence(tmp_path, [target], target/'evidence')
    with pytest.raises(ValueError, match='fresh'):
        cleanup.export_evidence(tmp_path, [target], tmp_path)


def test_tracked_files_refused(tmp_path, monkeypatch):
    target = tmp_path/'tests/runs'
    target.mkdir(parents=True)
    monkeypatch.setattr(cleanup.subprocess, 'check_output', lambda *a, **kw: b'tests/runs/important.json\0')
    with pytest.raises(ValueError, match='tracked source'):
        cleanup.validate_ignored(tmp_path, [target])


def test_large_evidence_is_losslessly_compressed(tmp_path):
    import gzip
    target = tmp_path/'tests/runs'
    target.mkdir(parents=True)
    data = b'known result\n' * 10000
    (target/'trial.log').write_bytes(data)
    destination = tmp_path/'evidence'
    records = cleanup.export_evidence(tmp_path, [target], destination)
    assert records[0]['stored_path'] == 'tests/runs/trial.log.gz'
    assert gzip.decompress((destination/records[0]['stored_path']).read_bytes()) == data
    assert records[0]['stored_bytes'] < len(data)
