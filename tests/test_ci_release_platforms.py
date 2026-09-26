"""Every supported platform and common exact source/WASM identity are mandatory."""
import copy
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ci_release_platforms as platforms
from ci_release_reuse import restore_tar
from native_target import target_metadata

SHA = 'a' * 40


def records():
    result = {}
    for name in platforms.PLATFORMS:
        target = target_metadata(name)
        result[name] = {'result': 'READY', 'source_commit': SHA,
                        'git_tag': 'v0.1.0-alpha.4', 'python_version': '0.1.0a4',
                        'guest_source_provenance': {k: 'b' * 64 for k in (
                            'wasm_sha256', 'prepared_source_sha256', 'toolchain_provenance_sha256', 'inputs_lock_sha256')},
                        'assets': {target['bundle_name'] + '.tar.gz': 'c' * 64,
                                   f"mariamem-0.1.0a4-py3-none-{target['wheel_platform']}.whl": 'd' * 64,
                                   'mariamem-0.1.0a4-corresponding-source.tar.gz': 'e' * 64},
                        'native_acceptance_sha256': 'f' * 64, 'wheel_acceptance_sha256': 'f' * 64}
    return result


def test_exact_platform_set_and_six_unique_assets():
    ready = platforms.aggregate_records(records(), SHA)
    assert ready['result'] == 'READY'
    assert ready['version'] == 2
    assert set(ready['assets']) == platforms.expected_names('0.1.0a4')
    assert len(ready['assets']) == 6
    assert all(platforms.source_name('0.1.0a4', p) in ready['assets'] for p in platforms.PLATFORMS)


@pytest.mark.parametrize('change', ['missing', 'failed', 'source', 'wasm', 'prepared', 'version', 'asset'])
def test_partial_or_mismatched_release_is_not_ready(change):
    data = records()
    ubuntu = data[platforms.UBUNTU]
    if change == 'missing':
        data.pop(platforms.UBUNTU)
    elif change == 'failed':
        ubuntu['result'] = 'NOT READY'
    elif change == 'source':
        ubuntu['source_commit'] = 'c' * 40
    elif change == 'wasm':
        ubuntu['guest_source_provenance']['wasm_sha256'] = 'd' * 64
    elif change == 'prepared':
        ubuntu['guest_source_provenance']['prepared_source_sha256'] = 'd' * 64
    elif change == 'version':
        ubuntu['python_version'] = '0.1.0a5'
    else:
        ubuntu['assets']['unaccepted.whl'] = 'f' * 64
    with pytest.raises(ValueError):
        platforms.aggregate_records(data, SHA)


def test_each_platform_uses_existing_guard_and_exact_checkout(tmp_path, monkeypatch):
    data = records()
    seen = []
    monkeypatch.setattr(platforms, 'check_public', lambda root: {'files': {'source.py': 'a' * 64}})
    def checked(commit, acceptance, root):
        seen.append((commit, root.name, acceptance.name))
        return data[root.name]
    monkeypatch.setattr(platforms, 'check_candidate', checked)
    platforms.check_aggregate(tmp_path, SHA)
    assert {name for _, name, _ in seen} == set(platforms.PLATFORMS)
    assert all(commit == SHA for commit, _, _ in seen)


def test_platform_checkout_drift_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(platforms, 'check_public', lambda root: {'files': {'source.py': str(root)}})
    with pytest.raises(ValueError, match='source checkout differs'):
        platforms.check_aggregate(tmp_path, SHA)


def test_handoff_platform_must_match_restore_target(tmp_path):
    path = tmp_path / 'input.tar'
    name = 'build/release/native-candidate/mariamem-native-ubuntu24.04-x86_64.tar.gz'
    with tarfile.open(path, 'w') as archive:
        item = tarfile.TarInfo(name); item.size = 1
        archive.addfile(item, io.BytesIO(b'x'))
    with pytest.raises(ValueError, match='unexpected candidate path'):
        restore_tar(path, tmp_path / 'wrong')
    restore_tar(path, tmp_path / 'correct', platform=platforms.UBUNTU)
    assert (tmp_path / 'correct' / name).read_bytes() == b'x'


def test_frozen_handoff_roundtrip_includes_only_allowed_inputs(tmp_path):
    root = tmp_path / 'checkout'
    platform = platforms.UBUNTU
    native = target_metadata(platform)['bundle_name'] + '.tar.gz'
    names = {
        'build/guest-aot/manifest.json': json.dumps({'platform': platform}),
        'build/guest-wasm/mariamem.wasm': 'wasm',
        'build/release/native-candidate/' + native: 'native',
        'build/release/native-candidate/native-candidate.json': '{}',
        'build/release/source-manifest.json': '{"file":"mariamem-0.1.0a4-source-candidate.tar.gz"}',
        'build/release/mariamem-0.1.0a4-source-candidate.tar.gz': 'source',
        'build/source-candidate-check.json': '{}',
        'build/dist/mariamem-0.1.0a4-py3-none-linux_x86_64.whl': 'wheel',
        'tests/evidence/alpha-wheel.json': '{"wheel":"build/dist/mariamem-0.1.0a4-py3-none-linux_x86_64.whl"}',
    }
    for name, body in names.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    # This build-local checksum must not leak into the handoff allowlist.
    (root / 'build/release/native-candidate/SHA256SUMS').write_text('build only')
    output = tmp_path / 'candidate-handoff.tar'
    platforms.handoff(root, platform, output)
    assert output.with_suffix('.sha256').read_text().strip() == platforms.digest(output)
    destination = tmp_path / 'restored'
    restore_tar(output, destination, platform=platform)
    for name, body in names.items():
        assert (destination / name).read_text() == body
    assert not (destination / 'build/release/native-candidate/SHA256SUMS').exists()
