"""Portable Linux boundary failures must be detected without running the guest."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import io
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_target
from wheel_metadata import check_description

spec = importlib.util.spec_from_file_location('linux_artifacts', ROOT / 'python/mariamem/_artifacts.py')
artifacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifacts)


def manifest(arch):
    return native_target.platform_fields(native_target.target_metadata('linux-' + arch))


@pytest.mark.parametrize('arch,machine', [('x86_64', 'x86_64'), ('aarch64', 'aarch64')])
def test_runtime_libc_and_cpu(monkeypatch, arch, machine):
    monkeypatch.setattr(artifacts.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(artifacts.platform, 'machine', lambda: machine)
    monkeypatch.setattr(artifacts.platform, 'libc_ver', lambda: ('glibc', '2.28'))
    assert artifacts._portable_linux(manifest(arch)) == 'linux-' + arch
    monkeypatch.setattr(artifacts.platform, 'libc_ver', lambda: ('glibc', '2.27'))
    with pytest.raises(artifacts.ArtifactError, match='unsupported glibc'):
        artifacts._portable_linux(manifest(arch))
    monkeypatch.setattr(artifacts.platform, 'libc_ver', lambda: ('', ''))
    monkeypatch.setattr(artifacts.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='', stderr='musl libc (test)\nVersion 1.2.2\n'))
    assert artifacts._portable_linux(manifest(arch)) == 'linux-' + arch
    monkeypatch.setattr(artifacts.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='', stderr='musl libc\nVersion 1.1.24\n'))
    with pytest.raises(artifacts.ArtifactError, match='unsupported musl'):
        artifacts._portable_linux(manifest(arch))
    other = 'aarch64' if arch == 'x86_64' else 'x86_64'
    with pytest.raises(artifacts.ArtifactError, match='CPU'):
        artifacts._portable_linux(manifest(other))


@pytest.mark.parametrize('arch,machine', [('x86_64', 'Advanced Micro Devices X86-64'), ('aarch64', 'AArch64')])
@pytest.mark.parametrize('bad', ['', 'interp', 'needed', 'symbols', 'cpu'])
def test_static_elf(monkeypatch, arch, machine, bad):
    outputs = [f'ELF64 little endian {machine}' if bad != 'cpu' else 'ELF64 little endian wrong',
               'INTERP' if bad == 'interp' else '',
               '(NEEDED) [libc.so.6]' if bad == 'needed' else '',
               'GLIBC_2.28' if bad == 'symbols' else '']
    monkeypatch.setattr(native_target.subprocess, 'check_output', lambda *a, **k: outputs.pop(0))
    target = native_target.target_metadata('linux-' + arch)
    if bad:
        with pytest.raises(ValueError):
            native_target.elf_dependencies(Path('host'), target)
    else:
        assert native_target.elf_dependencies(Path('host'), target)['static']


@pytest.mark.parametrize('body', ['', 'Description-Content-Type: text/plain\n\nHello', 'Description-Content-Type: text/markdown\n\n', 'Description-Content-Type: text/markdown\n\n# Hello'])
def test_description_missing_or_valid(body):
    with zipfile.ZipFile(io.BytesIO(), 'w') as archive:
        archive.writestr('mariamem.dist-info/METADATA', body)
        if body.endswith('# Hello'):
            check_description(archive)
        else:
            with pytest.raises(ValueError):
                check_description(archive)


def test_portable_manifest_is_validated_before_launch(tmp_path, monkeypatch):
    import hashlib
    import json
    monkeypatch.setattr(artifacts.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(artifacts.platform, 'machine', lambda: 'aarch64')
    monkeypatch.setattr(artifacts.platform, 'libc_ver', lambda: ('glibc', '2.28'))
    monkeypatch.setattr(artifacts, 'NATIVE_ROOT', tmp_path)
    monkeypatch.delenv('MARIAMEM_NATIVE_DIR', raising=False)
    host = tmp_path/'mariamem-host'
    host.write_bytes(b'host fixture')
    host.chmod(0o755)
    value = dict(manifest('aarch64'), version=1, runtime_kind='generated-go',
                 sha256={'mariamem-host': hashlib.sha256(host.read_bytes()).hexdigest()})
    (tmp_path/'manifest.json').write_text(json.dumps(value))
    assert artifacts.resolve()['host_binary'] == str(host)
    host.write_bytes(b'wrong bytes')
    with pytest.raises(artifacts.ArtifactError, match='hash mismatch'):
        artifacts.resolve()
    value['minimum_glibc'] = '2.17'
    (tmp_path/'manifest.json').write_text(json.dumps(value))
    with pytest.raises(artifacts.ArtifactError, match='minimum conditions'):
        artifacts.resolve()


def test_second_libc_failure_keeps_failure_receipt(tmp_path, monkeypatch):
    import hashlib
    import json
    import subprocess
    import linux_wheel_acceptance as acceptance
    (tmp_path/'tests/evidence').mkdir(parents=True)
    receipts = tmp_path/'build/linux-receipts'
    receipts.mkdir(parents=True)
    wheel = tmp_path/'wheel.whl'
    wheel.write_bytes(b'one immutable wheel')
    (tmp_path/'tests/evidence/alpha-wheel.json').write_text(json.dumps(dict(
        wheel=wheel.name, sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
        source_commit='a'*40, manifest={'package_version': '0.6.2'})))
    (receipts/'source.json').write_text(json.dumps({'source_commit': 'a'*40}))
    (tmp_path/'tests/consumer').mkdir()
    (tmp_path/'tests/consumer/test_database.py').write_text('')
    (tmp_path/'scripts').mkdir()
    (tmp_path/'scripts/pypi_smoke.py').write_text('')
    monkeypatch.setattr(acceptance, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['accept', '--target', 'linux-x86_64', '--arch', 'x86_64'])
    monkeypatch.setattr(acceptance.os, 'uname', lambda: SimpleNamespace(machine='x86_64'))
    monkeypatch.setattr(acceptance.subprocess, 'check_output', lambda *a, **k: json.dumps([
        dict(Architecture='amd64', Id='sha256:image', RepoDigests=['quay@sha256:digest'])]))
    calls = []

    def run(command, **kw):
        if command[1] == 'run':
            calls.append(command)
            if len(calls) == 2:
                raise subprocess.CalledProcessError(1, command)
            return SimpleNamespace(stdout='{"machine":"x86_64"}\n')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(acceptance.subprocess, 'run', run)
    with pytest.raises(subprocess.CalledProcessError):
        acceptance.main()
    assert json.loads((receipts/'manylinux_2_28.json').read_text())['result'] == 'PASS'
    assert json.loads((receipts/'musllinux_1_2.json').read_text())['result'] == 'FAIL'
    assert all('/input/wheel.whl' in command[-1] for command in calls)
