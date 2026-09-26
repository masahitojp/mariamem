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
        "version": 1, "minimum_macos": 15, "sha256": hashes,
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
