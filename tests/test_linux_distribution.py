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
    wheel = tmp_path/'mariamem-0.6.2-py3-none-manylinux_2_28_x86_64.musllinux_1_2_x86_64.whl'
    value = dict(manifest('x86_64'), package_version='0.6.2', sha256={'mariamem-host': hashlib.sha256(b'host').hexdigest()})
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('mariamem/_native/manifest.json', json.dumps(value))
        archive.writestr('mariamem/_native/mariamem-host', b'host')
    (tmp_path/'tests/evidence/alpha-wheel.json').write_text(json.dumps(dict(
        wheel=wheel.name, sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
        source_commit='a'*40, manifest=value)))
    (receipts/'source.json').write_text(json.dumps({'source_commit': 'a'*40}))
    (tmp_path/'tests/consumer').mkdir()
    (tmp_path/'tests/consumer/test_database.py').write_text('')
    (tmp_path/'scripts').mkdir()
    (tmp_path/'scripts/pypi_smoke.py').write_text('')
    monkeypatch.setattr(acceptance, 'ROOT', tmp_path)
    monkeypatch.setattr(acceptance, 'inspect_ref', lambda *a: SimpleNamespace(source_commit='a'*40))
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
            return SimpleNamespace(stdout=json.dumps(dict(machine='x86_64', cases=dict(tests=2,failures=0,errors=0,skipped=0)))+'\n')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(acceptance.subprocess, 'run', run)
    with pytest.raises(subprocess.CalledProcessError):
        acceptance.main()
    assert json.loads((receipts/'manylinux_2_28.json').read_text())['result'] == 'PASS'
    assert json.loads((receipts/'musllinux_1_2.json').read_text())['result'] == 'FAIL'
    assert all('/input/'+wheel.name in command[-1] for command in calls)


@pytest.mark.parametrize('arch', ['x86_64', 'aarch64'])
def test_real_packager_preserves_both_linux_tags_and_description(tmp_path, arch):
    import json
    import os
    import shutil
    import subprocess
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
    meta = native_target.target_metadata('linux-' + arch)
    (native / 'mariamem-host').write_bytes(b'inert host fixture')
    (native / 'manifest.json').write_text(json.dumps(dict(manifest(arch), version=1,
        runtime_kind='generated-go', package_version='0.6.2')))
    subprocess.run([sys.executable, 'setup.py', 'bdist_wheel'], cwd=project,
        env={**os.environ, 'MARIAMEM_WHEEL_PLATFORM': meta['wheel_platform']},
        check=True, capture_output=True, timeout=30)
    wheels = list((project / 'dist').glob('*.whl'))
    assert len(wheels) == 1 and wheels[0].name.endswith('-' + meta['wheel_platform'] + '.whl')
    with zipfile.ZipFile(wheels[0]) as archive:
        tags = archive.read('mariamem-0.6.2.dist-info/WHEEL').decode()
        for tag in meta['wheel_platform'].split('.'):
            assert 'Tag: py3-none-' + tag in tags
        description = check_description(archive)
        assert description.get_payload().strip() == (project / 'README.md').read_text().strip()
