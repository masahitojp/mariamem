"""Package binding and acceptance evidence checks without executing a runtime."""
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from fast_tranche_acceptance import clean_env, verify_guest_check, verify_inputs


def test_guest_key_evidence_requires_real_callback_and_no_generation():
    good = {'prepared_auth_keys': 'PASS', 'generated': False, 'actual_callback': True}
    assert verify_guest_check('valid', 0, json.dumps(good), '') == good
    for changed in ({'generated': True}, {'actual_callback': False}, {'prepared_auth_keys': 'FAIL'}):
        with pytest.raises(ValueError):
            verify_guest_check('valid', 0, json.dumps({**good, **changed}), '')
    with pytest.raises(ValueError):
        verify_guest_check('valid', 1, json.dumps(good), '')
    error = 'mariamem: bundled RSA keys failed. Reinstall/rebuild the complete matching native bundle.'
    assert verify_guest_check('missing', 18, '', error)['rejected']
    assert verify_guest_check('corrupt', 11, '', error)['rejected']
    for code, stderr in ((0, error), (18, 'unrelated crash')):
        with pytest.raises(ValueError):
            verify_guest_check('missing', code, '', stderr)


def test_consumer_environment_has_no_native_or_python_fallback(tmp_path, monkeypatch):
    for name in ('MARIAMEM_NATIVE_DIR', 'WASMER_DIR', 'PYTHONPATH', 'PYTEST_ADDOPTS',
                 'GOFLAGS', 'GOWORK', 'PIP_FIND_LINKS', 'VIRTUAL_ENV', 'GITHUB_TOKEN'):
        monkeypatch.setenv(name, 'untrusted')
    env = clean_env(tmp_path)
    assert all(value != 'untrusted' for value in env.values())
    assert Path(env['TMPDIR']).is_dir()
    assert env['GIT_CONFIG_GLOBAL'] == os.devnull


def packaged(tmp_path, different_module=False, corrupt_host=False):
    native = tmp_path / 'native'
    native.mkdir()
    files = {'wasmer-headless': b'runtime', 'mariamem.wasmu': b'module'}
    files['mariamem.wasmu.json'] = json.dumps({
        'snapshot_version': 1, 'wasm_sha256': '1' * 64,
        'module_sha256': hashlib.sha256(files['mariamem.wasmu']).hexdigest()}).encode()
    manifest = {'version': 1, 'platform': 'darwin-arm64', 'minimum_macos': 15,
                'package_version': '0.1.0', 'public_release_ready': False,
                'sha256': {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}
    for name, data in files.items():
        (native / name).write_bytes(data)
    (native / 'wasmer-headless').chmod(0o755)
    (native / 'manifest.json').write_text(json.dumps(manifest))
    files['mariamem-host'] = b'python host'
    if different_module:
        files['mariamem.wasmu'] = b'different module'
    wheel_manifest = {**manifest, 'sha256': {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}
    if corrupt_host:
        files['mariamem-host'] = b'tampered host'
    wheel = tmp_path / 'sample.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        for name, data in {**files, 'manifest.json': json.dumps(wheel_manifest).encode()}.items():
            archive.writestr('sample.data/purelib/mariamem/_native/' + name, data)
    return native, wheel


def test_package_binding_understands_go_archive_omits_host(tmp_path):
    native, wheel = packaged(tmp_path)
    result = verify_inputs(native, wheel, 'darwin-arm64')
    assert result['shared_native_bytes_match']
    assert 'mariamem-host' in result['wheel_manifest']['sha256']


@pytest.mark.parametrize('mode', ['different_module', 'corrupt_host'])
def test_package_binding_rejects_drift(tmp_path, mode):
    native, wheel = packaged(tmp_path, **{mode: True})
    with pytest.raises(ValueError, match='bytes differ|hash mismatch'):
        verify_inputs(native, wheel, 'darwin-arm64')
