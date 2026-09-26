#!/usr/bin/env python3
"""Fail closed while the alpha's concrete release checks remain unresolved."""
import json
import shutil
import tarfile
import zipfile
import os
from common import ROOT, digest
from check_public import check
from check_version import check_release_docs
from runtime_notices import verify as verify_runtime_notices
from release_version import PYTHON_VERSION, SOURCE_CANDIDATE, CORRESPONDING_SOURCE, GIT_TAG, require_tag


def artifact_versions(native, wheel):
    with tarfile.open(native, "r:gz") as archive:
        members = [item for item in archive.getmembers() if item.name.endswith("/manifest.json")]
        if len(members) != 1 or not members[0].isfile():
            raise ValueError("native archive manifest is missing or ambiguous")
        native_version = json.load(archive.extractfile(members[0]))["package_version"]
    with zipfile.ZipFile(wheel) as archive:
        metadata = archive.read(f"mariamem-{PYTHON_VERSION}.dist-info/METADATA").decode()
        wheel_version = next((line.removeprefix("Version: ") for line in metadata.splitlines()
                              if line.startswith("Version: ")), None)
    if native_version != PYTHON_VERSION or wheel_version != PYTHON_VERSION:
        raise ValueError("native or wheel package version differs from the canonical release version")


if os.environ.get("MARIAMEM_RELEASE_TAG"):
    require_tag(os.environ["MARIAMEM_RELEASE_TAG"])

source = check()
review = json.loads((ROOT / "release/review.json").read_text())
missing = [f"{name}: {item['note']}" for name, item in review["checks"].items()
           if not item.get("passed") or not item.get("evidence")]
try:
    check_release_docs()
except (ValueError, OSError) as error:
    missing.append("release-facing documentation: " + str(error))
try:
    verify_runtime_notices()
except (ValueError, KeyError, OSError) as error:
    missing.append("runtime notice evidence: " + str(error))
record_path = ROOT / "build/release/source-manifest.json"
if not record_path.exists():
    missing.append("source candidate has not been generated")
else:
    record = json.loads(record_path.read_text())
    if record.get("file") != SOURCE_CANDIDATE:
        missing.append("source candidate filename does not match the canonical release version")
    if record["manifest"]["files"] != source["files"]:
        missing.append("source candidate is stale; regenerate it after changes")
    archive = record_path.parent / record["file"]
    if not archive.exists() or digest(archive) != record["sha256"]:
        missing.append("source archive is missing or has a different hash")
    verification = ROOT / "build/source-candidate-check.json"
    if not verification.exists():
        missing.append("run scripts/verify_source.py for this source candidate")
    else:
        verified = json.loads(verification.read_text())
        if not verified.get("passed") or verified.get("source_candidate_sha256") != record["sha256"]:
            missing.append("source candidate verification is missing or stale")
wheel_path = ROOT / "tests/evidence/alpha-wheel.json"
alpha_path = ROOT / "tests/evidence/alpha.json"
if not wheel_path.exists() or not alpha_path.exists():
    missing.append("wheel build and installed-wheel acceptance evidence are required")
else:
    wheel = json.loads(wheel_path.read_text())
    alpha = json.loads(alpha_path.read_text())
    path = ROOT / wheel["wheel"]
    wheel_platform = json.loads((ROOT / "python/deployment_target.json").read_text())["wheel_platform"]
    if path.name != f"mariamem-{PYTHON_VERSION}-py3-none-{wheel_platform}.whl":
        missing.append("wheel filename does not match the canonical release version")
    if wheel["manifest"].get("package_version") != PYTHON_VERSION:
        missing.append("wheel build manifest does not match the canonical release version")
    if not path.exists() or digest(path) != wheel["sha256"]:
        missing.append("wheel hash differs from build evidence")
    if not wheel["manifest"].get("public_release_ready"):
        missing.append("rebuild the wheel after completing the release reviews")
    if not alpha.get("passed") or alpha.get("wheel_sha256") != wheel["sha256"]:
        missing.append("installed-wheel acceptance must identify this exact wheel hash")
native = ROOT / "build/release/native-candidate/mariamem-native-darwin-arm64.tar.gz"
platform_evidence = review["checks"]["platform_acceptance"].get("evidence")
if not platform_evidence:
    missing.append("native bundle has no platform acceptance evidence")
else:
    try:
        accepted = json.loads((ROOT / platform_evidence).read_text())
        accepted_hash = accepted["archive"]["sha256"]
        if (accepted["mode"] != "acceptance" or accepted["result"] != "PASS"
                or accepted["platform_acceptance_passed"] is not True
                or accepted["archive"]["filename"] != native.name
                or accepted["archive"]["expected_sha256"] != accepted_hash
                or accepted["environment"]["architecture"] != "arm64"
                or not accepted["environment"]["product_version"].startswith("15.")
                or not all(step["status"] == "PASS" for step in accepted["steps"].values())
                or digest(native) != accepted_hash):
            missing.append("native bundle differs from clean-platform accepted archive")
        elif path.exists():
            artifact_versions(native, path)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, tarfile.TarError) as error:
        missing.append("native bundle acceptance evidence is missing or invalid: " + str(error))
if missing:
    print("Source repository check: PASS\nBinary alpha publication: NOT READY")
    for message in missing:
        print("- " + message)
    raise SystemExit(1)
target = ROOT / "build/release/publish"
target.mkdir(exist_ok=True)
if any(target.iterdir()):
    raise SystemExit("build/release/publish is not empty; move the previous staged release aside")
source_name = CORRESPONDING_SOURCE
shutil.copy2(archive, target / source_name)
shutil.copy2(path, target / path.name)
shutil.copy2(native, target / native.name)
assets = {native.name: digest(target / native.name), path.name: digest(target / path.name),
          source_name: digest(target / source_name)}
manifest = {"version": 1, "release": PYTHON_VERSION, "git_tag": GIT_TAG, "assets": assets,
            "source_manifest": record["manifest"], "wheel": wheel, "acceptance": alpha,
            "native_acceptance": accepted, "reviews": review}
(ROOT / "build/release/release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
(target / "SHA256SUMS").write_text("".join(f"{value}  {name}\n" for name, value in assets.items()))
print("Recorded release checks passed; review assets in build/release/publish before publishing.")
