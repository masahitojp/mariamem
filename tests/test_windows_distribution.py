"""Windows target, wheel manifest and executable identity without a runtime build."""
import hashlib
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_target as target
from mariamem import _artifacts as artifacts


def pe(arch):
    data = bytearray(128)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<H', data, 68, 0xAA64 if arch == 'arm64' else 0x8664)
    struct.pack_into('<H', data, 88, 0x20B)
    return bytes(data)


@pytest.mark.parametrize('name,process,arch,tag', [
    (target.WINDOWS_X86, 'win-amd64', 'x86_64', 'win_amd64'),
    (target.WINDOWS_ARM, 'win-arm64', 'arm64', 'win_arm64'),
])
def test_windows_target_pe_and_installed_resolution(tmp_path, monkeypatch, name, process, arch, tag):
    with patch.object(target.platform, 'system', return_value='Windows'), patch.object(target.sysconfig, 'get_platform', return_value=process):
        actual = target.current_target()
    assert actual['wheel_platform'] == tag
    binary = tmp_path / 'mariamem-host.exe'
    binary.write_bytes(pe(arch))
    binary.chmod(0o755)
    assert target.pe_dependencies(binary, actual)['architecture'] == arch
    manifest = {'version': 1, **target.platform_fields(actual), 'runtime_kind': 'generated-go',
                'sha256': {binary.name: hashlib.sha256(binary.read_bytes()).hexdigest()}}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(artifacts, 'NATIVE_ROOT', tmp_path)
    monkeypatch.setattr(artifacts.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(artifacts.sysconfig, 'get_platform', lambda: process)
    monkeypatch.setattr(artifacts.sys, 'getwindowsversion', lambda: SimpleNamespace(build=22000), raising=False)
    assert artifacts.resolve()['host_binary'] == str(binary.resolve())
    assert target.manifest_target(manifest) == actual
    binary.write_bytes(pe('x86_64' if arch == 'arm64' else 'arm64'))
    with pytest.raises(ValueError, match='architecture'):
        target.pe_dependencies(binary, actual)
    with pytest.raises(artifacts.ArtifactError, match='hash mismatch'):
        artifacts.resolve()
    manifest['architecture'] = 'wrong'
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(artifacts.ArtifactError, match='CPU'):
        artifacts.resolve()


def test_windows_minimum_build_and_process_cpu(monkeypatch):
    monkeypatch.setattr(artifacts.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(artifacts.sysconfig, 'get_platform', lambda: 'win-arm64')
    monkeypatch.setattr(artifacts.sys, 'getwindowsversion', lambda: SimpleNamespace(build=21999), raising=False)
    with pytest.raises(artifacts.ArtifactError, match='22000'):
        artifacts._platform_identity()
    monkeypatch.setattr(artifacts.sysconfig, 'get_platform', lambda: 'win32')
    with pytest.raises(artifacts.ArtifactError, match='unsupported platform'):
        artifacts._platform_identity()


@pytest.mark.parametrize('data', [b'', b'not a PE', b'MZ' + b'\0' * 62])
def test_invalid_windows_executable_rejected(tmp_path, data):
    binary = tmp_path / 'host.exe'
    binary.write_bytes(data)
    with pytest.raises(ValueError, match='PE'):
        target.pe_dependencies(binary, target.target_metadata(target.WINDOWS_X86))


@pytest.mark.parametrize('name', [target.WINDOWS_X86, target.WINDOWS_ARM])
def test_real_packager_preserves_windows_wheel_tag(tmp_path, name):
    import os
    import shutil
    import subprocess
    import zipfile
    meta = target.target_metadata(name)
    project = tmp_path / 'package'
    native = project / 'mariamem/_native'
    native.mkdir(parents=True)
    for filename in ('setup.py', 'setup.cfg', 'deployment_target.json', 'README.md'):
        shutil.copyfile(ROOT / 'python' / filename, project / filename)
    (project / 'mariamem/__init__.py').write_text('')
    shutil.copyfile(ROOT / 'python/mariamem/_version.py', project / 'mariamem/_version.py')
    (project / 'license-inventory.json').write_text(json.dumps({'distributed_notices': []}))
    for filename in ('LICENSE', 'NOTICE', 'THIRD_PARTY_LICENSES'):
        (project / filename).write_text('inert packaging fixture')
    (native / 'mariamem-host.exe').write_bytes(pe(meta['architecture']))
    manifest = {'version': 1, **target.platform_fields(meta), 'runtime_kind': 'generated-go', 'package_version': '0.6.2'}
    (native / 'manifest.json').write_text(json.dumps(manifest))
    subprocess.run([sys.executable, 'setup.py', 'bdist_wheel'], cwd=project,
                   env={**os.environ, 'MARIAMEM_WHEEL_PLATFORM': meta['wheel_platform']},
                   check=True, capture_output=True, timeout=30)
    wheels = list((project / 'dist').glob('*.whl'))
    assert len(wheels) == 1 and wheels[0].name.endswith('-' + meta['wheel_platform'] + '.whl')
    with zipfile.ZipFile(wheels[0]) as archive:
        tag = archive.read('mariamem-0.6.2.dist-info/WHEEL').decode()
        assert 'Tag: py3-none-' + meta['wheel_platform'] in tag
        manifest_name = next(n for n in archive.namelist() if n.endswith('mariamem/_native/manifest.json'))
        host_name = next(n for n in archive.namelist() if n.endswith('mariamem/_native/mariamem-host.exe'))
        assert archive.read(manifest_name) == json.dumps(manifest).encode()
        assert archive.read(host_name) == pe(meta['architecture'])
