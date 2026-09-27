"""Reuse is exact-input measurement behavior, not a release provenance shortcut."""
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import benchmark_artifacts as reuse
from common import ROOT, digest
from test_ci_guest_source import fixture, write_json
from ci_guest_source import verify_ci_guest_source
from guest_experiment import patch_files


def inputs_tree(tmp_path):
    root = tmp_path / 'checkout'
    for name in (*reuse.RECIPE, 'release/inputs.lock.json'):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copytree(ROOT / 'guest', root / 'guest')
    return root


def test_guest_identity_ignores_harness_but_changes_for_patch_recipe_and_pins(tmp_path):
    root = inputs_tree(tmp_path)
    before = reuse.guest_inputs(root)
    (root / 'README.md').write_text('measurement-only change')
    assert reuse.guest_inputs(root) == before
    for name in ('guest/source.patch', 'guest/test-auth-keypair.json',
                 'scripts/prepare_guest.py', 'scripts/guest_auth_hooks.py',
                 'scripts/prepared_auth_keys.py', 'release/inputs.lock.json'):
        path = root / name
        original = path.read_bytes()
        if name == 'release/inputs.lock.json':
            changed = json.loads(original)
            changed['toolchain']['wasixcc'] = 'changed'
            write_json(path, changed)
        else:
            path.write_bytes(original + b'\nchange')
        assert reuse.guest_inputs(root) != before
        path.write_bytes(original)
    lock_path = root / 'release/inputs.lock.json'
    lock = json.loads(lock_path.read_text())
    lock['toolchain']['wasmer'] = 'runtime-only-change'
    write_json(lock_path, lock)
    assert reuse.guest_inputs(root) == before
    (root / 'guest/experimental.patch').write_text('temporary source change')
    assert reuse.guest_inputs(root) != before


def test_cpu_runtime_and_platform_change_only_aot_identity(tmp_path, monkeypatch):
    root, _, stage, _ = fixture(tmp_path)
    for name in ('scripts/compile_guest_aot.py', 'scripts/native_target.py',
                 'scripts/common.py', 'scripts/benchmark_artifacts.py'):
        dest = root / name
        dest.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(ROOT / name, dest)
    before = reuse.aot_inputs(stage / 'guest-wasm', 'ubuntu24.04-x86_64', root)
    import compile_guest_aot
    monkeypatch.setattr(compile_guest_aot, 'compile_command', lambda *args: ['w', 'compile', 'i', '-o', 'o', '-m', 'avx'])
    assert reuse.aot_inputs(stage / 'guest-wasm', 'ubuntu24.04-x86_64', root) != before
    assert reuse.aot_inputs(stage / 'guest-wasm', 'darwin-arm64', root) != before
    monkeypatch.setitem(reuse.LOCK['toolchain'], 'wasmer', 'different')
    assert reuse.aot_inputs(stage / 'guest-wasm', 'ubuntu24.04-x86_64', root) != before


def reusable_fixture(tmp_path, monkeypatch):
    root, _, stage, records = fixture(tmp_path)
    monkeypatch.setattr(reuse, 'ROOT', root)
    import compile_guest_aot
    monkeypatch.setattr(compile_guest_aot, 'ROOT', root)
    # Match fake tree's overlay hash, then update canonical nested records.
    records['guest-wasm-provenance.json']['build_configuration'] = {'jobs': 3}
    write_json(stage / 'guest-wasm/provenance.json', records['guest-wasm-provenance.json'])
    identity = {'test': 'exact-inputs'}
    monkeypatch.setattr(reuse, 'guest_inputs', lambda *args, **kwargs: identity)
    monkeypatch.setattr(reuse.subprocess, 'check_output',
        lambda argv, **kwargs: (root / 'release/inputs.lock.json').read_bytes()
        if argv[:2] == ['git', 'show'] else 'a' * 40 + '\n')
    reuse.stamp(stage / 'guest-wasm', identity)
    return root, stage, records


def test_verified_wasm_reuse_and_corruption_rejection(tmp_path, monkeypatch):
    root, stage, records = reusable_fixture(tmp_path, monkeypatch)
    directory = stage / 'guest-wasm'
    assert reuse.verify_wasm(directory)['wasm_sha256'] == digest(directory / 'mariamem.wasm')
    (directory / 'mariamem.wasm').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='file/hash mismatch'):
        reuse.verify_wasm(directory)


def test_input_mismatch_rejected_without_rebuild(tmp_path, monkeypatch):
    _, stage, _ = reusable_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(reuse, 'guest_inputs', lambda *args, **kwargs: {'different': True})
    with pytest.raises(ValueError, match='input identity mismatch'):
        reuse.verify_wasm(stage / 'guest-wasm')


def test_provenance_corruption_and_missing_cache_fail(tmp_path, monkeypatch):
    _, stage, _ = reusable_fixture(tmp_path, monkeypatch)
    path = stage / 'guest-wasm/toolchain.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='file/hash mismatch'):
        reuse.verify_wasm(path.parent)
    with pytest.raises(FileNotFoundError):
        reuse.verify_seal(tmp_path / 'missing', {})


def test_experimental_patch_branch_and_paths(tmp_path):
    (tmp_path / 'guest').mkdir()
    path = tmp_path / 'guest/experimental.patch'
    path.write_text('--- a/engine.cc\n+++ b/engine.cc\n')
    with patch('guest_experiment.subprocess.check_output', return_value='main\n'):
        with pytest.raises(ValueError, match='experiment/ branch'):
            patch_files(tmp_path)
    with patch('guest_experiment.subprocess.check_output', return_value='experiment/test\n'):
        assert patch_files(tmp_path) == ['engine.cc']
        path.write_text('+++ b/../unsafe\n')
        with pytest.raises(ValueError, match='unsafe'):
            patch_files(tmp_path)


def test_release_rejects_experimental_guest_provenance(tmp_path):
    root, lock, stage, records = fixture(tmp_path)
    prepared = records['prepared-source.json']
    prepared['experimental_patch'] = {'sha256': 'x'}
    write_json(stage / 'guest-wasm/prepared-source.json', prepared)
    with pytest.raises(ValueError, match='experimental guest'):
        verify_ci_guest_source(root, lock, stage)


def test_verified_aot_reuse_and_wrong_handoff_rejection(tmp_path, monkeypatch):
    _, stage, records = reusable_fixture(tmp_path, monkeypatch)
    directory = stage / 'guest-aot'
    expected = {'wasm_sha256': digest(stage / 'guest-wasm/mariamem.wasm'),
                'runtime': {'sha256': records['guest-aot-provenance.json']['wasmer_archive_sha256']},
                'package_version': reuse.PYTHON_VERSION, 'wasmer': reuse.LOCK['toolchain']['wasmer'], 'recipe': {}}
    monkeypatch.setattr(reuse, 'aot_inputs', lambda *args: expected)
    manifest = json.loads((directory / 'manifest.json').read_text())
    manifest['package_version'] = reuse.PYTHON_VERSION
    write_json(directory / 'manifest.json', manifest)
    record = records['guest-aot-provenance.json']
    record['native_manifest_sha256'] = digest(directory / 'manifest.json')
    record['wasm_handoff_provenance_sha256'] = digest(stage / 'guest-wasm/provenance.json')
    write_json(directory / 'provenance.json', record)
    reuse.stamp(directory, expected)
    assert reuse.verify_aot(directory, stage / 'guest-wasm', 'darwin-arm64')['aot_sha256'] == digest(directory / 'mariamem.wasmu')
    record['wasm_sha256_verified'] = '0' * 64
    write_json(directory / 'provenance.json', record)
    reuse.stamp(directory, expected)
    with pytest.raises(ValueError, match='handoff provenance mismatch'):
        reuse.verify_aot(directory, stage / 'guest-wasm', 'darwin-arm64')


def test_release_handoff_still_rejects_other_commit(tmp_path, monkeypatch):
    _, stage, _ = reusable_fixture(tmp_path, monkeypatch)
    import compile_guest_aot
    monkeypatch.setattr(compile_guest_aot.subprocess, 'check_output', lambda *args, **kwargs: 'b' * 40 + '\n')
    with pytest.raises(ValueError, match='source commit differs'):
        compile_guest_aot.verify_handoff(stage / 'guest-wasm')


def test_runtime_distribution_change_leaves_wasm_and_other_platform_identity(tmp_path, monkeypatch):
    root = inputs_tree(tmp_path)
    (root / 'python').mkdir()
    shutil.copyfile(ROOT / 'python/deployment_target.json', root / 'python/deployment_target.json')
    for name in ('scripts/compile_guest_aot.py', 'scripts/native_target.py'):
        shutil.copyfile(ROOT / name, root / name)
    wasm_dir = tmp_path / 'wasm'
    wasm_dir.mkdir()
    (wasm_dir / 'mariamem.wasm').write_bytes(b'wasm')
    (wasm_dir / 'provenance.json').write_text('{}')
    before_guest = reuse.guest_inputs(root)
    before_mac = reuse.aot_inputs(wasm_dir, 'darwin-arm64', root)
    before_ubuntu = reuse.aot_inputs(wasm_dir, 'ubuntu24.04-x86_64', root)
    lock = json.loads((root / 'release/inputs.lock.json').read_text())
    runtime = next(entry for entry in lock['inputs'] if entry['name'] == 'wasmer-linux-x86_64')
    runtime['sha256'] = '0' * 64
    write_json(root / 'release/inputs.lock.json', lock)
    monkeypatch.setattr(reuse, 'LOCK', lock)
    assert reuse.guest_inputs(root) == before_guest
    assert reuse.aot_inputs(wasm_dir, 'darwin-arm64', root) == before_mac
    assert reuse.aot_inputs(wasm_dir, 'ubuntu24.04-x86_64', root) != before_ubuntu
    compile_script = root / 'scripts/compile_guest_aot.py'
    compile_script.write_text(compile_script.read_text() + '\n# CPU recipe change\n')
    assert reuse.guest_inputs(root) == before_guest
