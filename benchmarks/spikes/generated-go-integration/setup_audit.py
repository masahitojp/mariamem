#!/usr/bin/env python3
"""Install the integration FD compatibility gate in an isolated generated module.

This is diagnostic infrastructure, not the production generation pipeline.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from patch_memfs import apply

BASE_SHA256 = "7d747bfb5114b80aac248ab0792f08a0f660f53c0859ba379ec8c3b36aff04f0"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-module", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source_module.resolve(), args.output.resolve()
    if output.exists():
        parser.error("output must be fresh")
    if (source / "go.mod").read_text().splitlines()[0] != "module example.com/mariamem-spike":
        parser.error("expected the accepted independent generated guest module")
    base = source / "generated/base/base.go"
    if hashlib.sha256(base.read_bytes()).hexdigest() != BASE_SHA256:
        parser.error("generated base differs from the accepted converter output")
    expected = json.loads(Path(__file__).with_name("accepted-generated-source.json").read_text())["files_sha256"]
    actual = {str(f.relative_to(source / "generated")): hashlib.sha256(f.read_bytes()).hexdigest()
              for f in (source / "generated").rglob("*") if f.is_file()}
    if actual != expected:
        parser.error("generated source/assembly inventory differs from the accepted converter output and bounded additions")
    patched_text = apply(base.read_text())
    output.mkdir(parents=True)
    shutil.copyfile(source / "go.mod", output / "go.mod")
    # Copy source only: never accidentally reuse an old executable or test result.
    shutil.copytree(source / "generated", output / "generated")
    patched = output / "generated/base/base.go"
    patched.write_text(patched_text)
    templates = Path(__file__).resolve().parent
    for template, destination in (
        ("io-driver.go.txt", "main.go"),
        ("readlink-contract-test.go.txt", "fs_contract_test.go"),
        ("io-audit-base.go.txt", "generated/base/audit.go"),
        ("relative-fd-base.go.txt", "generated/base/relative.go"),
        ("relative-fd-contract-test.go.txt", "generated/base/relative_contract_test.go"),
    ):
        shutil.copyfile(templates / template, output / destination)
    print("Installed FD audit. Stable directory-object adaptation installed; FD contracts must PASS.")


if __name__ == "__main__":
    main()
