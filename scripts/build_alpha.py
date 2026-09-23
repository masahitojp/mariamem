#!/usr/bin/env python3
"""Build/stage a local platform alpha; does not publish anything."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--go", type=Path, default=Path(shutil.which("go") or "go"))
parser.add_argument("--runtime", type=Path, default=ROOT / "build/tools/wasmer/bin/wasmer-headless")
parser.add_argument("--module", type=Path, default=ROOT / "build/guest/mariamem.wasmu")
args = parser.parse_args()
if platform.system() != "Darwin" or platform.machine() != "arm64":
    raise SystemExit("The initial alpha bundle is built on macOS arm64 only")
(ROOT / "build").mkdir(exist_ok=True)
(ROOT / "tests/evidence").mkdir(parents=True, exist_ok=True)
host = ROOT / "build/mariamem-host"
subprocess.run([str(args.go), "build", "-trimpath", "-o", str(host), "./cmd/mariamem-host"],
               cwd=ROOT, check=True, env=dict(os.environ, CGO_ENABLED="0", GOTOOLCHAIN="local",
                                             GOCACHE=str(ROOT / "build/gocache")))
native = ROOT / "python/mariamem/_native"
native.mkdir(parents=True, exist_ok=True)
for source, name in [(host, "mariamem-host"), (args.runtime, "wasmer-headless"),
                     (args.module, "mariamem.wasmu"), (Path(str(args.module)+".json"), "mariamem.wasmu.json")]:
    shutil.copy2(source, native / name)
for name in ("mariamem-host", "wasmer-headless"):
    (native / name).chmod(0o755)
major = int(platform.mac_ver()[0].split(".")[0])
review = json.loads((ROOT / "release/review.json").read_text())
ready = all(item.get("passed") and item.get("evidence") for item in review["checks"].values())
manifest = {"version": 1, "package_version": "0.1.0a1", "platform": "darwin-arm64",
            "minimum_macos": major, "wasmer_version": "7.4.2", "public_release_ready": bool(ready),
            "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in native.iterdir() if p.name != "manifest.json"}}
(native / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES"):
    shutil.copy2(ROOT / name, ROOT / "python" / name)
shutil.copytree(ROOT / "licenses", ROOT / "python/licenses", dirs_exist_ok=True)
subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                "--no-cache-dir", "--wheel-dir", str(ROOT / "build/dist"), str(ROOT / "python")],
               check=True, env=dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK="1",
                                    MARIAMEM_WHEEL_PLATFORM=f"macosx_{major}_0_arm64"))
print(json.dumps(manifest, indent=2))
wheel = ROOT / "build/dist" / f"mariamem-0.1.0a1-py3-none-macosx_{major}_0_arm64.whl"
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES", "Go-BSD-3-Clause.txt",
                 "Wasmer-MIT.txt", "wolfSSL-LICENSING.txt"):
        assert any(p.endswith(".dist-info/" + name) for p in names), f"missing {name}"
    for license_file in (ROOT / "licenses").iterdir():
        if license_file.is_file():
            entries = [p for p in names if p.endswith(".dist-info/" + license_file.name)]
            assert len(entries) == 1, f"missing license: {license_file.name}"
            assert archive.read(entries[0]) == license_file.read_bytes(), license_file.name
    for name, expected in manifest["sha256"].items():
        paths = [p for p in names if p.endswith("/mariamem/_native/" + name)]
        assert len(paths) == 1, name
        assert hashlib.sha256(archive.read(paths[0])).hexdigest() == expected, name
    assert not any("/mysqlmem/" in p for p in names), "old package leaked into wheel"
    evidence = {"wheel": str(wheel.relative_to(ROOT)), "bytes": wheel.stat().st_size,
                "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "files": names, "manifest": manifest, "archive_checks_passed": True}
(ROOT / "tests/evidence/alpha-wheel.json").write_text(json.dumps(evidence, indent=2) + "\n")
