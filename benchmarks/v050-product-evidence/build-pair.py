"""Build unchanged fixed runtimes for the approved paired product campaign."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--workspace", type=Path, required=True)
p.add_argument("--go-root", type=Path, required=True)
a = p.parse_args()
work = a.workspace.resolve()
compiler = a.go_root / "bin/go"
env = dict(os.environ, GOTOOLCHAIN="local", CGO_ENABLED="1",
           GOPATH=str(work / "temp/go-path"), GOMODCACHE=str(work / "temp/go-mod"),
           GOCACHE=str(work / "temp/go-cache"), GOTMPDIR=str(work / "temp/go-tmp"))
Path(env["GOTMPDIR"]).mkdir(exist_ok=True)
version = subprocess.check_output([compiler, "version"], env=env, text=True).strip()
assert version == "go version go1.26.8 darwin/arm64", version
flags = ["-p", "1", "-trimpath", "-buildvcs=false"]
receipt = {"go": version, "flags": flags, "CGO_ENABLED": "1", "states": {}}
sources = {"v047": ("baseline", "e0be06f3a20c72cbb5a9be27971280c80a3ec357"),
           "v050": ("candidate", "bb637c49e6d6b50ec6761dead172a35f0b051f7e")}
for state, (directory, source) in sources.items():
    root = work / "temp" / directory
    identity = json.loads(subprocess.check_output(
        ["python3", "scripts/git_identity.py", "inspect", "HEAD"], cwd=root, text=True))
    assert identity["source_commit"] == source and identity["object_type"] == "commit"
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
    binaries = work / "temp/binaries" / state
    binaries.mkdir(parents=True)
    for target, package in (("mariamem-host", "./cmd/mariamem-host"),
                            ("ownedprepared", "./benchmarks/ownedprepared")):
        print("BUILD", state, target, flush=True)
        command = [str(compiler), "build", *flags, "-o", str(binaries / target), package]
        subprocess.run(command, cwd=root, env=env, check=True)
    receipt["states"][state] = {
        "source_commit": source,
        "tree_sha": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip(),
        "guest": json.loads((root / "release/generated-go-inputs.json").read_text())["guest_sha256"],
        "generated_provenance_sha256": hashlib.sha256(
            (root / "internal/generatedgo/provenance.json").read_bytes()).hexdigest(),
        "binary_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in binaries.iterdir()},
        "go_build_info": {f.name: subprocess.check_output([compiler, "version", "-m", str(f)], text=True)
                          for f in binaries.iterdir()},
    }
baseline = work / "temp/baseline"
candidate = work / "temp/candidate"
for name in ("benchmarks/ownedprepared/main.go", "benchmarks/ownedprepared/resources.go",
             "benchmarks/python_product_suites.py"):
    assert (baseline / name).read_bytes() == (candidate / name).read_bytes(), name
receipt["identical_observers"] = True
helper = work / "temp/binaries/process-cost"
subprocess.run(["cc", "-O2", str(candidate / "benchmarks/tools/process_cost.c"), "-o", str(helper)], check=True)
receipt["process_helper_sha256"] = hashlib.sha256(helper.read_bytes()).hexdigest()
receipt["cc_version"] = subprocess.check_output(["cc", "--version"], text=True)
(work / "evidence/build-pair.json").write_text(json.dumps(receipt, indent=2) + "\n")
print("PASS: both fixed runtimes built with identical observers", flush=True)
