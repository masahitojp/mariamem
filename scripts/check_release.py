#!/usr/bin/env python3
"""Fail closed while the alpha's concrete release checks remain unresolved."""
import json
import shutil
from common import ROOT, digest
from check_public import check
from runtime_notices import verify as verify_runtime_notices

source = check()
review = json.loads((ROOT / "release/review.json").read_text())
missing = [f"{name}: {item['note']}" for name, item in review["checks"].items()
           if not item.get("passed") or not item.get("evidence")]
try:
    verify_runtime_notices()
except (ValueError, KeyError, OSError) as error:
    missing.append("runtime notice evidence: " + str(error))
record_path = ROOT / "build/release/source-manifest.json"
if not record_path.exists():
    missing.append("source candidate has not been generated")
else:
    record = json.loads(record_path.read_text())
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
    if not path.exists() or digest(path) != wheel["sha256"]:
        missing.append("wheel hash differs from build evidence")
    if not wheel["manifest"].get("public_release_ready"):
        missing.append("rebuild the wheel after completing the release reviews")
    if not alpha.get("passed") or alpha.get("wheel_sha256") != wheel["sha256"]:
        missing.append("installed-wheel acceptance must identify this exact wheel hash")
if missing:
    print("Source repository check: PASS\nBinary alpha publication: NOT READY")
    for message in missing:
        print("- " + message)
    raise SystemExit(1)
target = ROOT / "build/release/publish"
target.mkdir(exist_ok=True)
if any(target.iterdir()):
    raise SystemExit("build/release/publish is not empty; move the previous staged release aside")
source_name = "mariamem-0.1.0a1-corresponding-source.tar.gz"
shutil.copy2(archive, target / source_name)
shutil.copy2(path, target / path.name)
assets = {source_name: digest(target / source_name), path.name: digest(target / path.name)}
manifest = {"version": 1, "release": "0.1.0a1", "assets": assets,
            "source_manifest": record["manifest"], "wheel": wheel, "acceptance": alpha,
            "reviews": review}
(target / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
assets["release-manifest.json"] = digest(target / "release-manifest.json")
(target / "SHA256SUMS").write_text("".join(f"{value}  {name}\n" for name, value in assets.items()))
print("Recorded release checks passed; review assets in build/release/publish before publishing.")
