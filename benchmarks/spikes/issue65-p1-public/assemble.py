#!/usr/bin/env python3
"""Checked fixed-origin runtime plus separately inventoried public host wiring.

No canonical provenance guard is relaxed. Installer runs from the guest's exact
source checkout; the resulting runtime is then an explicit host-stage input.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GUEST = "d4f30818c3410db186db5ef1c9abc5f14af0cdc52bb2b76bbca369e02eb1b481"
ORIGIN = "be244a0bdb510a22417241c2aa2f76a9093aac1b"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--guest-workspace", type=Path, required=True)
    parser.add_argument("--stage", choices=("translate", "install", "compile"), required=True)
    args = parser.parse_args()
    w = args.workspace.resolve()
    guest_work = args.guest_workspace.resolve()
    origin = guest_work / "worktree"
    sys.path.insert(0, str(origin / "scripts"))
    from dev_guest import verify_guest, verify_translation, source_identity, inventory, CONTRACT
    from build_generated_guest import download
    from common import digest
    # These calls validate original source/guest independently of new host code.
    original = source_identity(origin)
    assert original["commit"] == ORIGIN
    record = verify_guest(origin, guest_work / "temp/artifact")
    assert record["source_commit"] == ORIGIN and record["guest_sha256"] == GUEST
    host_origin = source_identity(ROOT)
    out = w / "temp/public"
    out.mkdir(exist_ok=True)
    env = dict(os.environ, GOCACHE=str(w / "temp/gocache"),
               GOMODCACHE=str(w / "temp/gomodcache"), GOTOOLCHAIN="go1.26.10",
               CGO_ENABLED="0", GOMAXPROCS="2", GOGC="50", GOWORK="off", GOFLAGS="")
    def run(argv, label, cwd=ROOT):
        with (w / "evidence" / (label + ".txt")).open("w") as log:
            subprocess.run([str(x) for x in argv], cwd=cwd, env=env, check=True,
                           stdout=log, stderr=subprocess.STDOUT)
    translation = out / "translation"
    integration = origin / "benchmarks/spikes/generated-go-integration"
    if args.stage == "translate":
        pin = json.loads((origin / "release/generated-go-toolchain.json").read_text())["archives"]["converter"]
        archive = download(pin, w / "temp/downloads")
        run([sys.executable, integration / "translate_guest.py", "--guest", guest_work / "temp/artifact/mariamem.wasm",
             "--guest-sha256", GUEST, "--converter-archive", archive, "--output", translation], "public-translation")
        verify_translation(origin, translation, GUEST)
        run([sys.executable, integration / "setup_candidate.py", "--source-only", "--source-module", translation / "module",
             "--guest", guest_work / "temp/artifact/mariamem.wasm", "--input-manifest", translation / "input-manifest.json",
             "--output", out / "candidate"], "public-source-adapter")
        return
    product = out / "product"
    if args.stage == "install":
        verify_translation(origin, translation, GUEST)
        module = out / "candidate/module"
        inputs = dict(contract=CONTRACT, result="UNQUALIFIED", guest_sha256=GUEST,
                      source_inventory=inventory(module), data_sha256=digest(module / "generated/data.bin"),
                      candidate_files_sha256={p.relative_to(module).as_posix(): digest(p)
                        for suffix in ("*.go", "*.s") for p in module.rglob(suffix)},
                      guest_directory=str(guest_work / "temp/artifact"), translation_directory=str(translation),
                      guest_record_sha256=digest(guest_work / "temp/artifact/guest.json"),
                      translation_record_sha256=digest(translation / "input-manifest.json"))
        inputs_path = out / "installation-inputs.json"
        inputs_path.write_text(json.dumps(inputs, indent=2) + "\n")
        for name in host_origin["files_sha256"]:
            if name.startswith("internal/generatedgo/"):
                continue
            target = product / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        runtime = product / "internal/generatedgo"
        run([sys.executable, origin / "scripts/generate_runtime.py", "--source-module", module,
             "--development-input", inputs_path, "--development-thread-binding",
             ROOT / "benchmarks/spikes/issue65-p1-timeout/binding/identity.json", "--output", runtime], "public-install")
        shutil.copy2(ROOT / "benchmarks/spikes/issue65-p1-timeout/runtime_wire.go.txt", runtime / "runtime_wire.go")
        shutil.copy2(HERE / "factory.go.txt", product / "internal/host/factory.go")
        shutil.copy2(HERE / "public_test.go.txt", product / "public_native_test.go")
        kind = product / "internal/runtimekind/kind.go"
        canonical = json.loads((ROOT / "release/generated-go-inputs.json").read_text())["guest_sha256"]
        text = kind.read_text()
        assert text.count('const GuestSHA256 = "' + canonical + '"') == 1
        kind.write_text(text.replace(canonical, GUEST))
        # A positive artifact must never enter the legacy session serializer.
        wire = product / "internal/mysqlwire/wire.go"
        text = wire.read_text()
        marker = "func Serve("
        start = text.index(marker)
        brace = text.index("{", start)
        text = text[:brace+1] + '\n panic("legacy wire route tripwire")\n' + text[brace+1:]
        wire.write_text(text)
        # Full source overlay inventory records the tripwire/factory/runtime and
        # public fixture, not just a claimed route/source identifier.
        run(["gofmt", "-w", runtime / "runtime_wire.go", product / "internal/host/factory.go",
             product / "public_native_test.go", wire], "public-gofmt")
        receipt = dict(contract="issue65-public-unqualified", host_source_commit=host_origin["commit"],
                       guest_origin_source_commit=ORIGIN, runtime_installer_source_commit=ORIGIN,
                       guest_sha256=GUEST, source_inventory=inventory(product),
                       installer_inputs_sha256=digest(inputs_path),
                       binding_sha256=digest(ROOT / "benchmarks/spikes/issue65-p1-timeout/binding/identity.json"))
        (w / "evidence/public-source.json").write_text(json.dumps(receipt, indent=2) + "\n")
        assert source_identity(ROOT) == host_origin
        return
    receipt = json.loads((w / "evidence/public-source.json").read_text())
    assert receipt["source_inventory"] == inventory(product)
    run(["go", "test", "-c", "-p", "1", "-trimpath", "-buildvcs=false", "-o", out / "public.test", "."], "public-compile", product)
    run(["go", "build", "-p", "1", "-trimpath", "-buildvcs=false", "-o", out / "mariamem-host", "./cmd/mariamem-host"], "public-host-compile", product)
    assert receipt["source_inventory"] == inventory(product)
    (w / "evidence/public-binaries.json").write_text(json.dumps({
        "public_test_sha256": digest(out / "public.test"), "host_sha256": digest(out / "mariamem-host"),
        "source_receipt_sha256": digest(w / "evidence/public-source.json"),
        "go_buildinfo": subprocess.check_output(["go", "version", "-m", str(out / "mariamem-host")], env=env, text=True),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
