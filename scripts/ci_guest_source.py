"""Verify the Linux WASM -> macOS AOT source/build boundary for future candidates.

This is separate from the recorded alpha.3 Docker-build provenance. It verifies
build-time records and exact artifacts, never post-build acceptance or review.
"""
import json
from pathlib import Path
import subprocess

from common import digest
from verify_guest_provenance import EVIDENCE as REVIEWED_SYSROOT


def _read(path):
    return json.loads(path.read_text())


def _same(actual, expected, label):
    if actual != expected:
        raise ValueError(f"CI guest source mismatch: {label}")


def verify_ci_guest_source(root, lock, evidence_dir, build_records=None):
    """Return verified build identity; ``evidence_dir`` contains both stage outputs.

    The directory has ``guest-wasm`` and ``guest-aot`` subdirectories. If
    ``build_records`` is supplied, require the independently transferred stage
    records to equal those embedded in the corresponding-source manifest.
    """
    root = Path(root)
    evidence_dir = Path(evidence_dir)
    wasm_dir = evidence_dir / "guest-wasm"
    aot_dir = evidence_dir / "guest-aot"
    lock_hash = digest(root / "release/inputs.lock.json")
    prepared_path = wasm_dir / "prepared-source.json"
    toolchain_path = wasm_dir / "toolchain.json"
    wasm_record_path = wasm_dir / "provenance.json"
    aot_record_path = aot_dir / "provenance.json"
    prepared = _read(prepared_path)
    toolchain = _read(toolchain_path)
    wasm_record = _read(wasm_record_path)
    aot_record = _read(aot_record_path)
    records = {"prepared-source.json": prepared, "toolchain.json": toolchain,
               "guest-wasm-provenance.json": wasm_record,
               "guest-aot-provenance.json": aot_record}
    if build_records is not None:
        _same(records, build_records, "source manifest build records")
    for name, record in (("toolchain", toolchain), ("guest WASM", wasm_record),
                         ("AOT", aot_record)):
        _same(record["version"], 1, f"{name} provenance version")
    _same(prepared["inputs_lock_sha256"], lock_hash, "prepared source lock")
    _same(wasm_record["inputs_lock_sha256"], lock_hash, "WASM source lock")
    _same(toolchain["inputs_lock_sha256"], lock_hash, "toolchain lock")
    _same(wasm_record["prepared_source_sha256"], digest(prepared_path), "prepared source hash")
    _same(wasm_record["prepared_source"], prepared, "prepared source record")
    _same(wasm_record["toolchain_provenance_sha256"], digest(toolchain_path), "toolchain record hash")
    _same(wasm_record["toolchain"], toolchain, "toolchain record")
    _same(aot_record["wasm_handoff_provenance_sha256"], digest(wasm_record_path), "WASM handoff hash")
    _same(aot_record["source_commit"], wasm_record["source_commit"], "AOT source commit")
    if (root / ".git").exists():
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        _same(wasm_record["source_commit"], commit, "checkout source commit")
    overlays = {p.name: digest(p) for p in sorted((root / "guest").iterdir()) if p.is_file()}
    _same(prepared["overlays"], overlays, "patches and overlays")
    _same(wasm_record["linux_architecture"], "x86_64", "Linux build architecture")
    _same(wasm_record["target"], "wasm32/WASIX", "WASM target")
    pin = lock["toolchain"]["wasixcc_linux_x86_64"]
    _same(toolchain["host"], "linux-x86_64", "toolchain architecture")
    _same(toolchain["target"], "wasm32/WASIX", "toolchain target")
    _same(toolchain["wasixcc_version"], lock["toolchain"]["wasixcc"], "WASIXCC version")
    _same(toolchain["wasixcc_archive_url"], pin["url"], "WASIXCC distribution")
    _same(toolchain["wasixcc_archive_sha256"], pin["sha256"], "WASIXCC archive hash")
    _same(aot_record["wasixcc_archive_sha256"], pin["sha256"], "AOT WASIXCC input")
    for record_key, lock_key in (("llvm_tag", "llvm"), ("binaryen_tag", "binaryen"),
                                 ("sysroot_tag", "wasix_sysroot"),
                                 ("sysroot_variant", "wasix_sysroot_variant")):
        _same(toolchain[record_key], lock["toolchain"][lock_key], record_key)
    # The old alpha.3 record documents the reviewed release payload, not this
    # guest build. Compare the *new* toolchain's complete installed inventory
    # and linked-library candidates against that independently reviewed payload.
    reviewed = _read(root / REVIEWED_SYSROOT)["sysroot"]
    _same(toolchain["sysroot_tag"], reviewed["tag"], "reviewed sysroot tag")
    _same(toolchain["sysroot_variant"], reviewed["variant"], "reviewed sysroot variant")
    _same(toolchain["sysroot"]["entries"], reviewed["comparison"]["entries"], "sysroot entry count")
    _same(toolchain["sysroot"]["inventory_sha256"],
          reviewed["comparison"]["inventory_sha256"], "reviewed sysroot payload")
    _same(toolchain["sysroot_major_libraries_sha256"], reviewed["major_library_sha256"],
          "reviewed sysroot libraries")
    wasm = wasm_dir / wasm_record["wasm_file"]
    _same(wasm.name, "mariamem.wasm", "guest WASM filename")
    _same(digest(wasm), wasm_record["wasm_sha256"], "guest WASM hash")
    _same(wasm.stat().st_size, wasm_record["wasm_bytes"], "guest WASM size")
    with wasm.open("rb") as stream:
        _same(stream.read(8), b"\0asm\1\0\0\0", "guest WASM header")
    _same((wasm_dir / "SHA256SUMS").read_text(),
          f"{wasm_record['wasm_sha256']}  {wasm.name}\n", "guest WASM checksum file")
    _same(aot_record["wasm_sha256_verified"], wasm_record["wasm_sha256"], "AOT input WASM")
    aot = aot_dir / "mariamem.wasmu"
    _same(digest(aot), aot_record["aot_sha256"], "AOT module hash")
    _same(aot.stat().st_size, aot_record["aot_bytes"], "AOT module size")
    sidecar = _read(aot_dir / "mariamem.wasmu.json")
    _same(sidecar["wasm_sha256"], wasm_record["wasm_sha256"], "AOT sidecar WASM")
    _same(sidecar["module_sha256"], aot_record["aot_sha256"], "AOT sidecar module")
    _same(sidecar["snapshot_version"], 1, "snapshot version")
    manifest_path = aot_dir / "manifest.json"
    manifest = _read(manifest_path)
    target = _read(root / "python/deployment_target.json")
    _same(manifest["version"], 1, "native manifest version")
    _same(manifest["minimum_macos"], target["minimum_macos"], "native macOS floor")
    _same(aot_record["macos_architecture"], "arm64", "AOT architecture")
    _same(aot_record["native_manifest_sha256"], digest(manifest_path), "AOT manifest hash")
    _same(manifest["sha256"]["mariamem.wasmu"], aot_record["aot_sha256"], "native AOT hash")
    _same(manifest["sha256"]["mariamem.wasmu.json"],
          digest(aot_dir / "mariamem.wasmu.json"), "native sidecar hash")
    _same(manifest["sha256"]["wasmer-headless"],
          digest(aot_dir / "wasmer-headless"), "native runtime hash")
    _same(aot_record["headless_executable_sha256"],
          manifest["sha256"]["wasmer-headless"], "AOT runtime hash")
    runtime = next(e for e in lock["inputs"] if e["name"] == "wasmer")
    _same(aot_record["wasmer_archive_sha256"], runtime["sha256"], "Wasmer distribution hash")
    if lock["toolchain"]["wasmer"] not in aot_record["wasmer_version"]:
        raise ValueError("CI guest source mismatch: Wasmer version")
    notice = _read(root / "release/wasmer-runtime-notices.json")
    _same(manifest["sha256"]["wasmer-headless"], notice["runtime_sha256"],
          "reviewed Wasmer runtime binary")
    _same(manifest["platform"], "darwin-arm64", "native platform")
    return {"version": 1, "source_commit": wasm_record["source_commit"],
            "inputs_lock_sha256": lock_hash,
            "prepared_source_sha256": digest(prepared_path),
            "toolchain_provenance_sha256": digest(toolchain_path),
            "reviewed_sysroot_asset_sha256": reviewed["sha256"],
            "wasm_sha256": wasm_record["wasm_sha256"],
            "aot_sha256": aot_record["aot_sha256"],
            "runtime_sha256": manifest["sha256"]["wasmer-headless"],
            "aot_provenance_sha256": digest(aot_record_path)}
