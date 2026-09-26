"""The future CI source review binds exact build outputs without alpha.3 state."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ci_guest_source import verify_ci_guest_source  # noqa: E402
from common import digest  # noqa: E402


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def fixture(tmp_path):
    root = tmp_path / "source"
    stage = tmp_path / "handoff"
    wasm_dir = stage / "guest-wasm"
    aot_dir = stage / "guest-aot"
    wasm_dir.mkdir(parents=True)
    aot_dir.mkdir(parents=True)
    (root / "guest").mkdir(parents=True)
    (root / "guest/source.patch").write_text("patch\n")
    lock = json.loads((ROOT / "release/inputs.lock.json").read_text())
    write_json(root / "release/inputs.lock.json", lock)
    write_json(root / "python/deployment_target.json", {"minimum_macos": 15})
    reviewed = json.loads((ROOT / "release/guest-source-provenance.json").read_text())
    write_json(root / "release/guest-source-provenance.json", reviewed)
    prepared = {"inputs_lock_sha256": digest(root / "release/inputs.lock.json"),
                "overlays": {"source.patch": digest(root / "guest/source.patch")},
                "modified_files": {"wasm/test.c": "test-hash"}}
    write_json(wasm_dir / "prepared-source.json", prepared)
    sysroot = reviewed["sysroot"]
    pin = lock["toolchain"]["wasixcc_linux_x86_64"]
    toolchain = {"version": 1, "host": "linux-x86_64", "target": "wasm32/WASIX",
                 "inputs_lock_sha256": prepared["inputs_lock_sha256"],
                 "wasixcc_version": lock["toolchain"]["wasixcc"],
                 "wasixcc_archive_url": pin["url"], "wasixcc_archive_sha256": pin["sha256"],
                 "llvm_tag": lock["toolchain"]["llvm"],
                 "binaryen_tag": lock["toolchain"]["binaryen"],
                 "sysroot_tag": sysroot["tag"], "sysroot_variant": sysroot["variant"],
                 "sysroot": {"entries": sysroot["comparison"]["entries"],
                             "inventory_sha256": sysroot["comparison"]["inventory_sha256"]},
                 "sysroot_major_libraries_sha256": sysroot["major_library_sha256"]}
    write_json(wasm_dir / "toolchain.json", toolchain)
    wasm = wasm_dir / "mariamem.wasm"
    wasm.write_bytes(b"\0asm\1\0\0\0")
    wasm_record = {"version": 1, "source_commit": "a" * 40,
                   "inputs_lock_sha256": prepared["inputs_lock_sha256"],
                   "prepared_source_sha256": digest(wasm_dir / "prepared-source.json"),
                   "prepared_source": prepared,
                   "toolchain_provenance_sha256": digest(wasm_dir / "toolchain.json"),
                   "toolchain": toolchain, "linux_architecture": "x86_64",
                   "target": "wasm32/WASIX", "wasm_file": wasm.name,
                   "wasm_sha256": digest(wasm), "wasm_bytes": wasm.stat().st_size}
    write_json(wasm_dir / "provenance.json", wasm_record)
    (wasm_dir / "SHA256SUMS").write_text(f"{digest(wasm)}  {wasm.name}\n")
    aot = aot_dir / "mariamem.wasmu"
    aot.write_bytes(b"compiled-module")
    headless = aot_dir / "wasmer-headless"
    headless.write_bytes(b"runtime")
    write_json(root / "release/wasmer-runtime-notices.json", {"runtime_sha256": digest(headless)})
    write_json(aot_dir / "mariamem.wasmu.json",
               {"wasm_sha256": digest(wasm), "module_sha256": digest(aot),
                "snapshot_version": 1})
    manifest = {"version": 1, "platform": "darwin-arm64", "minimum_macos": 15, "sha256": {
        "mariamem.wasmu": digest(aot),
        "mariamem.wasmu.json": digest(aot_dir / "mariamem.wasmu.json"),
        "wasmer-headless": digest(headless)}}
    write_json(aot_dir / "manifest.json", manifest)
    wasmer = next(e for e in lock["inputs"] if e["name"] == "wasmer")
    aot_record = {"version": 1, "source_commit": wasm_record["source_commit"],
                  "macos_architecture": "arm64",
                  "wasm_handoff_provenance_sha256": digest(wasm_dir / "provenance.json"),
                  "wasm_sha256_verified": digest(wasm),
                  "wasixcc_archive_sha256": pin["sha256"],
                  "wasmer_archive_sha256": wasmer["sha256"],
                  "wasmer_version": "wasmer " + lock["toolchain"]["wasmer"],
                  "headless_executable_sha256": digest(headless),
                  "aot_sha256": digest(aot), "aot_bytes": aot.stat().st_size,
                  "native_manifest_sha256": digest(aot_dir / "manifest.json")}
    write_json(aot_dir / "provenance.json", aot_record)
    records = {"prepared-source.json": prepared, "toolchain.json": toolchain,
               "guest-wasm-provenance.json": wasm_record,
               "guest-aot-provenance.json": aot_record}
    return root, lock, stage, records


def test_exact_ci_guest_source_boundary(tmp_path):
    root, lock, stage, records = fixture(tmp_path)
    verified = verify_ci_guest_source(root, lock, stage, records)
    assert verified["source_commit"] == "a" * 40
    assert verified["wasm_sha256"] == digest(stage / "guest-wasm/mariamem.wasm")


@pytest.mark.parametrize("change,matching", [
    ("guest-wasm/mariamem.wasm", "guest WASM hash"),
    ("guest-aot/mariamem.wasmu", "AOT module hash"),
    ("guest-aot/wasmer-headless", "native runtime hash"),
])
def test_rejects_changed_artifact(tmp_path, change, matching):
    root, lock, stage, records = fixture(tmp_path)
    (stage / change).write_bytes(b"different")
    with pytest.raises(ValueError, match=matching):
        verify_ci_guest_source(root, lock, stage, records)


def test_rejects_record_not_in_corresponding_source(tmp_path):
    root, lock, stage, records = fixture(tmp_path)
    records["guest-wasm-provenance.json"] = {"different": True}
    with pytest.raises(ValueError, match="source manifest build records"):
        verify_ci_guest_source(root, lock, stage, records)


def test_rejects_unreviewed_sysroot(tmp_path):
    root, lock, stage, _ = fixture(tmp_path)
    path = stage / "guest-wasm/toolchain.json"
    toolchain = json.loads(path.read_text())
    toolchain["sysroot"]["inventory_sha256"] = "0" * 64
    write_json(path, toolchain)
    wasm_path = stage / "guest-wasm/provenance.json"
    wasm_record = json.loads(wasm_path.read_text())
    wasm_record["toolchain"] = toolchain
    wasm_record["toolchain_provenance_sha256"] = digest(path)
    write_json(wasm_path, wasm_record)
    aot_path = stage / "guest-aot/provenance.json"
    aot_record = json.loads(aot_path.read_text())
    aot_record["wasm_handoff_provenance_sha256"] = digest(wasm_path)
    write_json(aot_path, aot_record)
    with pytest.raises(ValueError, match="reviewed sysroot payload"):
        verify_ci_guest_source(root, lock, stage)


def ubuntu_fixture(tmp_path):
    root, lock, stage, _ = fixture(tmp_path)
    aot_dir = stage / "guest-aot"
    path = aot_dir / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest.update(platform="ubuntu24.04-x86_64", distribution="ubuntu", version_id="24.04", architecture="x86_64")
    del manifest["minimum_macos"]
    write_json(path, manifest)
    record_path = aot_dir / "provenance.json"
    record = json.loads(record_path.read_text())
    del record["macos_architecture"]
    record.update(aot_platform="ubuntu24.04-x86_64", aot_architecture="x86_64",
                  linux_os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
                  runtime_dependencies={"format": "ELF-x86_64", "manylinux_verified": False,
                                        "wheel_platform": "linux_x86_64", "glibc_versions": ["2.17", "2.39"]},
                  native_manifest_sha256=digest(path),
                  wasmer_archive_sha256=next(e for e in lock["inputs"] if e["name"] == "wasmer-linux-x86_64")["sha256"])
    write_json(record_path, record)
    write_json(root / "release/wasmer-linux-runtime-notices.json", {"runtime_sha256": digest(aot_dir / "wasmer-headless")})
    return root, lock, stage


def test_exact_ubuntu_ci_guest_source_boundary(tmp_path):
    root, lock, stage = ubuntu_fixture(tmp_path)
    result = verify_ci_guest_source(root, lock, stage)
    assert result["runtime_sha256"] == digest(stage / "guest-aot/wasmer-headless")


@pytest.mark.parametrize("change, matching", [
    ("distribution", "candidate platform"), ("runtime", "native runtime hash"),
    ("aot_os", "AOT distribution"), ("glibc", "GLIBC exceeds"),
])
def test_rejects_ubuntu_provenance_mismatch(tmp_path, change, matching):
    root, lock, stage = ubuntu_fixture(tmp_path)
    aot_dir = stage / "guest-aot"
    if change == "runtime":
        (aot_dir / "wasmer-headless").write_bytes(b"changed")
    elif change == "distribution":
        path = aot_dir / "manifest.json"
        record = json.loads(path.read_text())
        record["distribution"] = "debian"
        write_json(path, record)
    else:
        path = aot_dir / "provenance.json"
        record = json.loads(path.read_text())
        if change == "aot_os":
            record["linux_os_release"]["ID"] = "debian"
        else:
            record["runtime_dependencies"]["glibc_versions"] = ["2.40"]
        write_json(path, record)
    with pytest.raises(ValueError, match=matching):
        verify_ci_guest_source(root, lock, stage)
