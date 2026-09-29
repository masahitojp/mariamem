"""Private release fixtures preserve runtime bytes and never change production versions."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('zero_fixture', ROOT / 'tests/consumer/run_zero_setup.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from release_version import PYTHON_VERSION


def test_release_like_fixture_is_private_and_keeps_runtime_identity(tmp_path):
    native = tmp_path / 'native'
    native.mkdir()
    for name, data in [('wasmer-headless', b'inert-runtime'), ('mariamem.wasmu', b'inert-aot')]:
        (native / name).write_bytes(data)
    (native / 'wasmer-headless').chmod(0o755)
    sidecar = {'snapshot_version': 1, 'module_sha256': hashlib.sha256(b'inert-aot').hexdigest(),
               'wasm_sha256': 'a' * 64}
    (native / 'mariamem.wasmu.json').write_text(json.dumps(sidecar))
    original = {'version': 1, 'platform': 'darwin-arm64', 'minimum_macos': 15,
                'package_version': PYTHON_VERSION,
                'sha256': {name: hashlib.sha256((native / name).read_bytes()).hexdigest()
                           for name in ('wasmer-headless', 'mariamem.wasmu', 'mariamem.wasmu.json')}}
    (native / 'manifest.json').write_text(json.dumps(original))
    work = tmp_path / 'work'
    work.mkdir()
    location, identity = fixture.prepare_fixture(ROOT, native, work)
    assert json.loads((native / 'manifest.json').read_text()) == original
    with tarfile.open(location / identity['asset'], 'r:gz') as archive:
        prefix = 'mariamem-native-darwin-arm64/'
        for name in original['sha256']:
            assert archive.extractfile(prefix + name).read() == (native / name).read_bytes()
        assert json.load(archive.extractfile(prefix + 'manifest.json'))['package_version'] == '0.3.0a999'
    assert identity['archive_sha256'] != identity['wrong_archive_sha256']
    assert fixture.TAG not in (ROOT / 'python/mariamem/_version.py').read_text()


def test_fixture_proxy_contains_exact_go_source_without_replace(tmp_path):
    proxy = fixture.prepare_proxy(ROOT, tmp_path)
    directory = proxy / fixture.MODULE / '@v'
    assert (directory / f'{fixture.TAG}.mod').read_bytes() == (ROOT / 'go.mod').read_bytes()
    with zipfile.ZipFile(directory / f'{fixture.TAG}.zip') as archive:
        prefix = f'{fixture.MODULE}@{fixture.TAG}/'
        for name in ('mariamem.go', 'native_version.go', 'internal/artifacts/download.go', 'release/inputs.lock.json'):
            assert archive.read(prefix + name) == (ROOT / name).read_bytes()
        assert all(not name.endswith('_test.go') for name in archive.namelist())


def test_v03_workflow_uses_verified_shared_guest_and_both_platforms():
    workflow = (ROOT / '.github/workflows/guest-build-boundary.yml').read_text()
    assert 'v03_acceptance:' in workflow
    assert '!inputs.v03_acceptance' in workflow
    assert '|| inputs.v03_acceptance' in workflow
    assert workflow.count('python scripts/build_guest_wasm.py') == 1
    for platform in ('darwin-arm64', 'ubuntu24.04-x86_64'):
        assert f'platform: {platform}' in workflow
    assert 'python scripts/v03_acceptance.py' in workflow
    assert 'tests/evidence/v03-*' in workflow
    assert 'contents: write' not in workflow and 'gh release create' not in workflow
