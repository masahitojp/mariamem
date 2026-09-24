#!/usr/bin/env python3
"""Prepare the source candidate offline outside the repository and compare inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from common import ROOT, LOCK, digest, extract
from runtime_sources import verify_runtime_sources

archive = ROOT / "build/release/mariamem-0.1.0a1-source-candidate.tar.gz"
record = json.loads((archive.parent / "source-manifest.json").read_text())
if digest(archive) != record["sha256"]:
    raise ValueError("source candidate archive hash mismatch")
expected = json.loads((ROOT / "build/prepared-source.json").read_text())["modified_files"]
with tempfile.TemporaryDirectory(prefix="mariamem-source-check-") as temporary:
    target = Path(temporary) / "unpack"
    extract(archive, target)
    project = target / "mariamem-0.1.0a1"
    subprocess.run([sys.executable, "scripts/check_public.py"], cwd=project, check=True)
    manifest = json.loads((project / "build/source-manifest.json").read_text())
    lock_path = project / "release/inputs.lock.json"
    if (digest(lock_path) != manifest["inputs_lock_sha256"]
            or digest(lock_path) != digest(ROOT / "release/inputs.lock.json")):
        raise ValueError("source candidate input lock is different or stale")
    bundled_lock = json.loads(lock_path.read_text())
    runtime_sources = verify_runtime_sources(project, bundled_lock)
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
          "wasix_sysroot_variant": LOCK["toolchain"]["wasix_sysroot_variant"],
          "sysroot_rebuild_verified": False}
(ROOT / "build/source-candidate-check.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
