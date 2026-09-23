#!/usr/bin/env python3
"""Collect a source candidate without silently declaring legal completeness."""
import gzip
import io
import json
import tarfile
from common import ROOT, LOCK, digest, fetch
from check_public import check, public_files

check()
out = ROOT / "build/release"
out.mkdir(parents=True, exist_ok=True)
review = json.loads((ROOT / "release/review.json").read_text())
archive = out / "mariamem-0.1.0a1-source-candidate.tar.gz"
inputs = [entry for entry in LOCK["inputs"] if entry.get("kind") != "runtime-binary"]
for entry in inputs:
    fetch(entry["name"])
manifest = {"version": 1, "source_complete": bool(review["checks"]["guest_source"].get("passed")),
            "review": review, "inputs_lock_sha256": digest(ROOT / "release/inputs.lock.json"),
            "files": {p.relative_to(ROOT).as_posix(): digest(p) for p in public_files()},
            "source_inputs": inputs}
provenance = [ROOT / "build" / name for name in
              ("prepared-source.json", "preparation-inputs.lock.json", "guest-build.json")]
manifest["build_records"] = {p.name: json.loads(p.read_text()) for p in provenance if p.exists()}
with archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
    with tarfile.open(fileobj=gz, mode="w") as tar:
        def add(path, name):
            info = tar.gettarinfo(str(path), arcname="mariamem-0.1.0a1/" + name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            with path.open("rb") as stream:
                tar.addfile(info, stream)
        for path in public_files():
            add(path, path.relative_to(ROOT).as_posix())
        for entry in inputs:
            add(ROOT / "build/downloads" / entry["file"], "build/downloads/" + entry["file"])
        content = (json.dumps(manifest, indent=2) + "\n").encode()
        info = tarfile.TarInfo("mariamem-0.1.0a1/build/source-manifest.json")
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
record = {"file": archive.name, "sha256": digest(archive), "bytes": archive.stat().st_size,
          "manifest": manifest}
(out / "source-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
print(f"Collected source candidate ({archive.stat().st_size} bytes); review remains required")
