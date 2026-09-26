"""Deterministic startup diagnostics without running a MariaDB guest."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

import mariamem
from mariamem import _artifacts


def bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(_artifacts.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(_artifacts.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(_artifacts.platform, "mac_ver", lambda: ("15.0", (), ""))
    monkeypatch.setenv("MARIAMEM_NATIVE_DIR", str(tmp_path))
    hashes = {}
    for name in ("mariamem-host", "wasmer-headless", "mariamem.wasmu"):
        path = tmp_path / name
        path.write_bytes(b"fixture")
        path.chmod(0o755)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps({
        "version": 1, "platform": "darwin-arm64", "minimum_macos": 15, "sha256": hashes,
    }))


def test_unsupported_platform(monkeypatch):
    monkeypatch.setattr(_artifacts.platform, "system", lambda: "Linux")
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start()
    assert failure.value.code == "unsupported_platform"
    assert failure.value.stage == "platform"
    assert failure.value.__cause__ is not None


def test_unsupported_macos_floor(tmp_path, monkeypatch):
    bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(_artifacts.platform, "mac_ver", lambda: ("12.5.1", (), ""))
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start()
    assert failure.value.code == "unsupported_platform"


@pytest.mark.parametrize("name", ["manifest.json", "wasmer-headless", "mariamem.wasmu"])
def test_missing_native_input(tmp_path, monkeypatch, name):
    bundle(tmp_path, monkeypatch)
    (tmp_path / name).unlink()
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start()
    assert failure.value.code == "native_unavailable"
    assert name in str(failure.value)


def test_artifact_mismatch(tmp_path, monkeypatch):
    bundle(tmp_path, monkeypatch)
    (tmp_path / "mariamem.wasmu").write_bytes(b"changed")
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start()
    assert failure.value.code == "artifact_mismatch"
    assert "mariamem.wasmu" in str(failure.value)


def host_options(tmp_path, body):
    host = tmp_path / "host"
    host.write_text(f"#!{sys.executable}\n" + body)
    host.chmod(0o755)
    runtime = tmp_path / "runtime"
    runtime.write_bytes(b"fixture")
    runtime.chmod(0o755)
    module = tmp_path / "guest"
    module.write_bytes(b"fixture")
    return dict(host_binary=host, runtime=runtime, module=module, shutdown_timeout=1)


def test_host_exec_failure_retains_os_cause(tmp_path):
    options = host_options(tmp_path, "")
    Path(options["host_binary"]).write_bytes(b"not an executable format")
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start(**options)
    assert failure.value.code == "host_start"
    assert failure.value.stage == "host_launch"
    assert isinstance(failure.value.__cause__, OSError)


def test_startup_frame_preserves_guest_stage(tmp_path):
    options = host_options(tmp_path, '''import json
print(json.dumps({"event":"error", "error":{"code":"guest_start", "stage":"guest_launch", "message":"Wasmer could not execute guest"}}), flush=True)
''')
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start(**options)
    assert failure.value.code == "guest_start"
    assert failure.value.stage == "guest_launch"
    assert failure.value.closed
    assert "Wasmer could not execute guest" in str(failure.value)


def test_startup_eof_keeps_exit_status_and_bounded_stderr(tmp_path):
    options = host_options(tmp_path, '''import sys
sys.stderr.write("x" * 5000 + "\\nloader failure\\n")
sys.exit(7)
''')
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start(**options)
    assert failure.value.code == "host_start"
    assert failure.value.stage == "host_ready"
    assert "exit status 7" in str(failure.value)
    assert "loader failure" in str(failure.value)
    assert len(str(failure.value)) < 2200
    assert failure.value.__cause__ is not None


def ubuntu_bundle(tmp_path, monkeypatch):
    bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(_artifacts.platform, "system", lambda: "Linux")
    monkeypatch.setattr(_artifacts.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(_artifacts, "_os_release", lambda: {"ID": "ubuntu", "VERSION_ID": "24.04"})
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest.update(platform="ubuntu24.04-x86_64", distribution="ubuntu", version_id="24.04", architecture="x86_64")
    del manifest["minimum_macos"]
    path.write_text(json.dumps(manifest))


def test_ubuntu_artifact_resolution(tmp_path, monkeypatch):
    ubuntu_bundle(tmp_path, monkeypatch)
    resolved = _artifacts.resolve()
    assert resolved["module"] == str(tmp_path / "mariamem.wasmu")


@pytest.mark.parametrize("release,arch", [
    ({"ID": "ubuntu", "VERSION_ID": "22.04"}, "x86_64"),
    ({"ID": "debian", "VERSION_ID": "24.04"}, "x86_64"),
    ({"ID": "linuxmint", "ID_LIKE": "ubuntu", "VERSION_ID": "24.04"}, "x86_64"),
    ({"ID": "ubuntu", "VERSION_ID": "24.04"}, "aarch64"),
])
def test_unsupported_linux_identity(tmp_path, monkeypatch, release, arch):
    ubuntu_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(_artifacts, "_os_release", lambda: release)
    monkeypatch.setattr(_artifacts.platform, "machine", lambda: arch)
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start()
    assert failure.value.code == "unsupported_platform"
    assert failure.value.stage == "platform"


@pytest.mark.parametrize("key", ["distribution", "version_id", "architecture", "platform"])
def test_ubuntu_manifest_identity_mismatch(tmp_path, monkeypatch, key):
    ubuntu_bundle(tmp_path, monkeypatch)
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest[key] = "wrong"
    path.write_text(json.dumps(manifest))
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start()
    assert failure.value.code == "artifact_mismatch"


def test_linux_explicit_inputs_keep_override_semantics(tmp_path, monkeypatch):
    options = host_options(tmp_path, "")
    monkeypatch.setattr(_artifacts.platform, "system", lambda: "Linux")
    monkeypatch.setattr(_artifacts.platform, "machine", lambda: "aarch64")
    resolved = _artifacts.resolve(**{key: options[key] for key in ("host_binary", "runtime", "module")})
    assert resolved["module"] == str(options["module"])
