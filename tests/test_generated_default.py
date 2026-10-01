"""Fast default selection and host-only packaging regressions."""
import hashlib
import json
from pathlib import Path
import pytest
from mariamem import _artifacts


def test_generated_bundle_needs_host_only(tmp_path, monkeypatch):
    host = tmp_path/'mariamem-host'
    host.write_bytes(b'fixture executable');host.chmod(0o700)
    manifest = {'version':1,'platform':'darwin-arm64','minimum_macos':15,
                'runtime_kind':'generated-go','sha256':{'mariamem-host':hashlib.sha256(host.read_bytes()).hexdigest()}}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setenv('MARIAMEM_NATIVE_DIR',str(tmp_path))
    monkeypatch.setattr(_artifacts,'_platform_identity',lambda:'darwin-arm64')
    monkeypatch.setattr(_artifacts.platform,'mac_ver',lambda:('15.0','',''))
    resolved=_artifacts.resolve()
    assert resolved == {'host_binary':str(host),'runtime':None,'module':None}
    host.write_bytes(b'corrupt')
    with pytest.raises(_artifacts.ArtifactError,match='hash mismatch'):_artifacts.resolve()


def test_explicit_host_does_not_discover_wasmer(tmp_path, monkeypatch):
    monkeypatch.delenv('MARIAMEM_NATIVE_DIR',raising=False)
    host=tmp_path/'host';host.write_bytes(b'fixture');host.chmod(0o700)
    monkeypatch.setattr(_artifacts,'_platform_identity',lambda:pytest.fail('bundle discovery'))
    assert _artifacts.resolve(host_binary=host)['runtime'] is None


def test_compiled_guest_identity_matches_recipe():
    root=Path(__file__).resolve().parents[1]
    pins=json.loads((root/'release/generated-go-inputs.json').read_text())
    sha=pins['guest_sha256']
    for name in ['internal/runtimekind/kind.go','internal/generatedgo/entry.go']:
        assert sha in (root/name).read_text()


def test_explicit_host_preserves_legacy_environment_bundle(tmp_path, monkeypatch):
    hashes={}
    for name in ['mariamem-host','wasmer-headless','mariamem.wasmu']:
        path=tmp_path/name;path.write_bytes(name.encode());path.chmod(0o700)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path/'manifest.json').write_text(json.dumps({'version':1,'platform':'darwin-arm64','minimum_macos':15,'sha256':hashes}))
    override=tmp_path/'custom-host';override.write_bytes(b'custom host');override.chmod(0o700)
    monkeypatch.setenv('MARIAMEM_NATIVE_DIR',str(tmp_path))
    monkeypatch.setattr(_artifacts,'_platform_identity',lambda:'darwin-arm64')
    monkeypatch.setattr(_artifacts.platform,'mac_ver',lambda:('15.0','',''))
    result=_artifacts.resolve(host_binary=override)
    assert result['host_binary']==str(override)
    assert result['runtime']==str(tmp_path/'wasmer-headless')
    assert result['module']==str(tmp_path/'mariamem.wasmu')
