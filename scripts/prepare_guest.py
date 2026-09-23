#!/usr/bin/env python3
"""Prepare a fresh MariaDB source tree from the public input lock and overlays."""
import json
import re
import shutil
import subprocess
from common import ROOT, LOCK, digest, extract, fetch

source = ROOT / "build/source"
if source.exists():
    raise SystemExit("build/source already exists; move it aside before preparing a fresh tree")
work = ROOT / "build/unpack"
work.mkdir(parents=True, exist_ok=False)
for name in ("lite4mariadb", "libmariadb", "wolfssl"):
    extract(fetch(name), work / name)
main = next((work / "lite4mariadb").iterdir())
shutil.move(str(main), source)
for name, relative in (("libmariadb", "libmariadb"), ("wolfssl", "extra/wolfssl/wolfssl")):
    target = source / relative
    if target.exists():
        target.rmdir()  # Only replace upstream's empty submodule placeholders.
    shutil.move(str(next((work / name).iterdir())), target)
for name, expected in LOCK["pristine_files"].items():
    if digest(source / name) != expected:
        raise ValueError(f"unexpected upstream file: {name}")
subprocess.run(["patch", "-p1", "-i", str(ROOT / "guest/source.patch")], cwd=source, check=True)
core = re.sub(r"\bg_mysql\b", "multi_mysql", (ROOT / "guest/wire_core.inc").read_text())
(source / "wasm/wire_api.inc").write_text(
    "#include <pthread.h>\nstatic _Thread_local MYSQL *multi_mysql;\n" + core + '\n#include "resident.inc"\n')
for name in ("resident.inc", "snapshot_fs.inc"):
    shutil.copy2(ROOT / "guest" / name, source / "wasm" / name)
vendor = source / "mariamem-dependencies"
vendor.mkdir()
for name, cmake in (("pcre2", "cmake/pcre.cmake"), ("libfmt", "cmake/libfmt.cmake")):
    entry = next(p for p in LOCK["inputs"] if p["name"] == name)
    shutil.copy2(fetch(name), vendor / entry["file"])
    path = source / cmake
    text = path.read_text()
    if text.count(entry["url"]) != 1:
        raise ValueError(f"unexpected dependency URL in {cmake}")
    path.write_text(text.replace(entry["url"], "${CMAKE_SOURCE_DIR}/mariamem-dependencies/" + entry["file"]))
manifest = {"inputs_lock_sha256": digest(ROOT / "release/inputs.lock.json"),
            "overlays": {p.name: digest(p) for p in sorted((ROOT / "guest").iterdir()) if p.is_file()},
            "modified_files": {name: digest(source / name) for name in
                               (*LOCK["pristine_files"], "wasm/wire_api.inc", "wasm/resident.inc",
                                "wasm/snapshot_fs.inc", "cmake/pcre.cmake", "cmake/libfmt.cmake")}}
(ROOT / "build/prepared-source.json").write_text(json.dumps(manifest, indent=2) + "\n")
shutil.copy2(ROOT / "release/inputs.lock.json", ROOT / "build/preparation-inputs.lock.json")
print("Prepared build/source from pinned archives; all guest dependencies are local.")
