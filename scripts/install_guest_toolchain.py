#!/usr/bin/env python3
"""Install the pinned Linux x86_64 WASIXCC toolchain for guest builds."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import urllib.request

from common import ROOT, LOCK, digest, extract


def inventory(root):
    entries = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries[name] = ["symlink", os.readlink(path)]
        elif path.is_file():
            entries[name] = ["file", digest(path)]
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {"entries": len(entries), "inventory_sha256": hashlib.sha256(encoded).hexdigest()}


def main():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("WASIXCC guest toolchain requires Linux x86_64")
    pin = LOCK["toolchain"]["wasixcc_linux_x86_64"]
    if LOCK["toolchain"]["wasixcc"] != "0.4.7":
        raise ValueError("unexpected WASIXCC version")
    home = Path.home() / ".wasixcc"
    bin_dir = home / "bin"
    if bin_dir.exists() and any(bin_dir.iterdir()):
        raise SystemExit(f"WASIXCC bin directory already populated: {bin_dir}")
    downloads = ROOT / "build/downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / "wasixcc-x86_64-unknown-linux-gnu.tar.gz"
    if not archive.exists():
        pending = archive.with_suffix(".partial")
        try:
            with urllib.request.urlopen(pin["url"], timeout=120) as response, pending.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            if digest(pending) != pin["sha256"]:
                raise ValueError("WASIXCC archive SHA256 mismatch")
            pending.replace(archive)
        finally:
            pending.unlink(missing_ok=True)
    if digest(archive) != pin["sha256"]:
        raise ValueError("WASIXCC archive SHA256 mismatch")
    tools = ROOT / "build/tools"
    tools.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tools, prefix="wasixcc-extract-") as temporary:
        unpack = Path(temporary) / "archive"
        extract(archive, unpack)
        bin_dir.mkdir(parents=True, exist_ok=True)
        for source in unpack.iterdir():
            target = bin_dir / source.name
            if source.is_dir():
                shutil.copytree(source, target, symlinks=True)
            else:
                shutil.copy2(source, target, follow_symlinks=False)
    driver = bin_dir / "wasixccenv"
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    subprocess.run([str(driver), "install-executables", str(bin_dir)], check=True, env=env)
    subprocess.run([str(driver), "download-all", "--llvm-tag", LOCK["toolchain"]["llvm"],
                    "--sysroot-tag", LOCK["toolchain"]["wasix_sysroot"],
                    "--binaryen-tag", LOCK["toolchain"]["binaryen"]], check=True, env=env)
    variant = LOCK["toolchain"]["wasix_sysroot_variant"]
    sysroot = home / "sysroot" / variant
    if not sysroot.is_dir():
        raise ValueError(f"missing installed sysroot: {sysroot}")
    selected = {}
    for name in ("bin/wasixccenv", "bin/wasixcc", "bin/wasixc++"):
        path = home / name
        if not path.exists():
            raise ValueError(f"missing toolchain executable: {name}")
        selected[name] = digest(path)
    for executable in ("clang", "wasm-opt"):
        matches = [p for p in home.rglob(executable) if p.is_file() and not p.is_relative_to(sysroot)]
        if not matches:
            raise ValueError(f"missing installed toolchain executable: {executable}")
        for path in matches:
            selected[path.relative_to(home).as_posix()] = digest(path)
    libraries = {}
    for name in ("libc.a", "libc++.a", "libc++abi.a", "libunwind.a",
                 "libclang_rt.builtins-wasm32.a", "crt1.o", "libwasi-emulated-mman.a",
                 "libwasi-emulated-process-clocks.a"):
        path = sysroot / "lib/wasm32-wasi" / name
        libraries[name] = digest(path)
    record = {
        "version": 1, "host": "linux-x86_64", "target": "wasm32/WASIX",
        "inputs_lock_sha256": digest(ROOT / "release/inputs.lock.json"),
        "wasixcc_version": LOCK["toolchain"]["wasixcc"],
        "wasixcc_archive_url": pin["url"], "wasixcc_archive_sha256": digest(archive),
        "llvm_tag": LOCK["toolchain"]["llvm"],
        "binaryen_tag": LOCK["toolchain"]["binaryen"],
        "sysroot_tag": LOCK["toolchain"]["wasix_sysroot"], "sysroot_variant": variant,
        "sysroot": inventory(sysroot), "sysroot_major_libraries_sha256": libraries,
        "selected_executables_sha256": selected,
    }
    output = tools / "wasixcc-linux-x86_64.json"
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
