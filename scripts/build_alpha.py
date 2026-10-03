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

from deployment import check_binary
from release_version import PYTHON_VERSION
from native_target import current_target, platform_fields, elf_dependencies

ROOT = Path(__file__).resolve().parents[1]
target = current_target(ROOT)
major = target.get("minimum_macos")
wheel_platform = target["wheel_platform"]
parser = argparse.ArgumentParser()
parser.add_argument("--go", type=Path, default=Path(shutil.which("go") or "go"))
parser.add_argument("--runtime", type=Path, default=None)
parser.add_argument("--module", type=Path, default=None)
parser.add_argument("--ci-candidate", action="store_true",
                    help="build immutable candidate metadata without post-build review state")
args = parser.parse_args()
if (args.runtime is None)!=(args.module is None): parser.error("legacy bundle requires --runtime and --module")
legacy=args.runtime is not None
(ROOT / "build").mkdir(exist_ok=True)
(ROOT / "tests/evidence").mkdir(parents=True, exist_ok=True)
host = ROOT / "build/mariamem-host"
subprocess.run([str(args.go), "build", "-p", "1", "-trimpath", "-o", str(host), "./cmd/mariamem-host"],
               cwd=ROOT, check=True, env=dict(os.environ, CGO_ENABLED="0", GOTOOLCHAIN="go1.26.8",
                                             GOOS=target["goos"], GOARCH=target["goarch"],
                                             **({"MACOSX_DEPLOYMENT_TARGET": f"{major}.0"}
                                                if major is not None else {}),
                                             GOCACHE=str(ROOT / "build/gocache")))
binary_minimums = ({p.name: check_binary(p, major) for p in ((host, args.runtime) if legacy else (host,))}
                   if major is not None else {})
linux_dependencies = ({p.name: elf_dependencies(p) for p in ((host, args.runtime) if legacy else (host,))}
                      if major is None else {})
native = ROOT / "python/mariamem/_native"
native.mkdir(parents=True, exist_ok=True)
sources=[(host,"mariamem-host")]
if legacy:
 sources += [(args.runtime,"wasmer-headless"),(args.module,"mariamem.wasmu"),(Path(str(args.module)+".json"),"mariamem.wasmu.json")]
else:
 for name in ("wasmer-headless","mariamem.wasmu","mariamem.wasmu.json"):
  (native/name).unlink(missing_ok=True)
for source, name in sources:
    shutil.copy2(source, native / name)
for name in (["mariamem-host","wasmer-headless"] if legacy else ["mariamem-host"]):
    (native / name).chmod(0o755)
ready = False
if not args.ci_candidate:
    review = json.loads((ROOT / "release/review.json").read_text())
    ready = all(item.get("passed") and item.get("evidence") for item in review["checks"].values())
manifest = {"version": 1, "package_version": PYTHON_VERSION, **platform_fields(target), "runtime_kind": "wasmer" if legacy else "generated-go", "guest_sha256": None if legacy else json.loads((ROOT/"release/generated-go-inputs.json").read_text())["guest_sha256"], "public_release_ready": bool(ready) if legacy else False,
            "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in native.iterdir() if p.name != "manifest.json"}}
(native / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES"):
    shutil.copy2(ROOT / name, ROOT / "python" / name)
shutil.copytree(ROOT / "licenses", ROOT / "python/licenses", dirs_exist_ok=True)
subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                "--no-cache-dir", "--wheel-dir", str(ROOT / "build/dist"), str(ROOT / "python")],
               check=True, env=dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK="1",
                                    MARIAMEM_WHEEL_PLATFORM=wheel_platform))
print(json.dumps(manifest, indent=2))
wheel = ROOT / "build/dist" / f"mariamem-{PYTHON_VERSION}-py3-none-{wheel_platform}.whl"
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    metadata = archive.read(f"mariamem-{PYTHON_VERSION}.dist-info/WHEEL").decode()
    assert f"Tag: py3-none-{wheel_platform}" in metadata, "incorrect wheel tag"
    bundled_manifest = next(p for p in names if p.endswith("/mariamem/_native/manifest.json"))
    assert json.loads(archive.read(bundled_manifest)) == manifest, "incorrect bundled manifest"
    # Modern setuptools may put license files under .dist-info/licenses/.
    # Check content in either standard location, not just filename presence.
    license_inputs = [ROOT / name for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES")]
    license_inputs += [p for p in (ROOT / "licenses").iterdir() if p.is_file()]
    for license_file in license_inputs:
        entries = [p for p in names if ".dist-info/" in p
                   and p.rsplit("/", 1)[-1] == license_file.name]
        assert entries, f"missing license: {license_file.name}"
        assert all(archive.read(entry) == license_file.read_bytes() for entry in entries), license_file.name
    for name, expected in manifest["sha256"].items():
        paths = [p for p in names if p.endswith("/mariamem/_native/" + name)]
        assert len(paths) == 1, name
        assert hashlib.sha256(archive.read(paths[0])).hexdigest() == expected, name
    assert not any("/mysqlmem/" in p for p in names), "old package leaked into wheel"
    evidence = {"wheel": str(wheel.relative_to(ROOT)), "bytes": wheel.stat().st_size,
                "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "binary_minimum_macos": binary_minimums, "linux_dependencies": linux_dependencies, "files": names, "manifest": manifest, "archive_checks_passed": True}
if args.ci_candidate and not legacy:
    from generated_release import checkout, source_inventory
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    checkout(ROOT, commit)
    buildinfo = subprocess.check_output([str(args.go), "version", "-m", str(host)], cwd=ROOT, text=True)
    if "vcs.revision="+commit not in buildinfo or "vcs.modified=false" not in buildinfo:
        raise ValueError("host executable is not built from the exact clean candidate")
    evidence.update(source_commit=commit, source_files_sha256=source_inventory(ROOT),
                    host_buildinfo=buildinfo)
(ROOT / "tests/evidence/alpha-wheel.json").write_text(json.dumps(evidence, indent=2) + "\n")
