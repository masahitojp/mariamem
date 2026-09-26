#!/usr/bin/env python3
"""Prepare the source candidate offline outside the repository and compare inputs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import runpy
from common import ROOT, LOCK, digest, extract
from ci_guest_source import verify_ci_guest_source
from runtime_sources import verify_runtime_sources
from verify_guest_provenance import verify_evidence
from release_version import SOURCE_ROOT, SOURCE_CANDIDATE

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--ci-evidence-dir", type=Path,
                    help="canonical Linux guest WASM and macOS AOT build outputs")
args = parser.parse_args()
archive = ROOT / "build/release" / SOURCE_CANDIDATE
record = json.loads((archive.parent / "source-manifest.json").read_text())
if record.get("file") != SOURCE_CANDIDATE:
    raise ValueError("source candidate filename differs from the canonical release version")
if digest(archive) != record["sha256"]:
    raise ValueError("source candidate archive hash mismatch")
if args.ci_evidence_dir:
    stage = args.ci_evidence_dir.resolve()
    expected = json.loads((stage / "guest-wasm/prepared-source.json").read_text())["modified_files"]
    current_provenance = verify_ci_guest_source(ROOT, LOCK, stage, record["manifest"]["build_records"])
    if current_provenance != record["manifest"]["guest_source_provenance"]:
        raise ValueError("CI guest source provenance differs from archive record")
else:
    expected = json.loads((ROOT / "build/prepared-source.json").read_text())["modified_files"]
with tempfile.TemporaryDirectory(prefix="mariamem-source-check-") as temporary:
    target = Path(temporary) / "unpack"
    extract(archive, target)
    project = target / SOURCE_ROOT
    bundled_version = runpy.run_path(str(project / "python/mariamem/_version.py"))["PYTHON_VERSION"]
    if bundled_version != SOURCE_ROOT.removeprefix("mariamem-"):
        raise ValueError("bundled version differs from the candidate archive name")
    subprocess.run([sys.executable, "scripts/check_public.py"], cwd=project, check=True)
    manifest = json.loads((project / "build/source-manifest.json").read_text())
    lock_path = project / "release/inputs.lock.json"
    if (digest(lock_path) != manifest["inputs_lock_sha256"]
            or digest(lock_path) != digest(ROOT / "release/inputs.lock.json")):
        raise ValueError("source candidate input lock is different or stale")
    bundled_lock = json.loads(lock_path.read_text())
    source_inputs = [entry for entry in bundled_lock["inputs"]
                     if entry.get("kind") != "runtime-binary"]
    if manifest["source_inputs"] != source_inputs:
        raise ValueError("source candidate input inventory differs from the lock")
    for entry in source_inputs:
        if digest(project / "build/downloads" / entry["file"]) != entry["sha256"]:
            raise ValueError(f"source candidate input hash mismatch: {entry['name']}")
    runtime_sources = verify_runtime_sources(project, bundled_lock)
    if args.ci_evidence_dir:
        if (manifest.get("build_path") != ("linux-x86_64-wasm/" + ("ubuntu24.04-x86_64-aot" if manifest["build_records"]["guest-aot-provenance.json"].get("aot_platform") == "ubuntu24.04-x86_64" else "macos-arm64-aot"))
                or manifest.get("review") is not None or manifest.get("source_complete") is not True):
            raise ValueError("invalid CI source candidate build path/review scope")
        guest_provenance = verify_ci_guest_source(project, bundled_lock, stage,
                                                  manifest["build_records"])
    else:
        guest_provenance = verify_evidence(project, bundled_lock, manifest["build_records"])
    if guest_provenance != manifest["guest_source_provenance"]:
        raise ValueError("guest provenance differs from candidate manifest")
    if runtime_sources != manifest["runtime_sources"]:
        raise ValueError("runtime source evidence differs from candidate manifest")
    if manifest["wasix_sysroot_variant"] != LOCK["toolchain"]["wasix_sysroot_variant"]:
        raise ValueError("source candidate sysroot variant mismatch")
    code = '''import sys, runpy, urllib.request
sys.path.insert(0, "scripts")
def offline(*args, **kwargs):
    raise RuntimeError("unexpected network access while preparing source candidate")
urllib.request.urlopen = offline
runpy.run_path("scripts/prepare_guest.py", run_name="__main__")
'''
    subprocess.run([sys.executable, "-c", code], cwd=project, check=True)
    for name, expected_hash in expected.items():
        if digest(project / "build/source" / name) != expected_hash:
            raise ValueError(f"source candidate differs from the built guest input: {name}")
report = {"passed": True, "source_candidate_sha256": digest(archive), "offline_prepare": True,
          "modified_files_match_built_guest": True, "files_checked": len(expected),
          "runtime_sources": runtime_sources,
          "guest_source_provenance": guest_provenance,
          "wasix_sysroot_variant": LOCK["toolchain"]["wasix_sysroot_variant"],
          "sysroot_rebuild_verified": False}
(ROOT / "build/source-candidate-check.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
