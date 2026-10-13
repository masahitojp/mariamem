"""Isolated native-width writer candidate; never installs canonical artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
module = out / "module"
module.mkdir()
for src in HERE.glob("*.txt"):
    shutil.copy2(src, module / src.name.removesuffix(".txt"))
mapping = ROOT / "internal/generatedgo/code/base/memory_mapping.go"
(module / "memory_mapping.go").write_text(mapping.read_text().replace("package base", "package narrow", 1))
(module / "go.mod").write_text("module example.com/narrowwriters\n\ngo 1.26.0\n")
env = dict(os.environ, GOTOOLCHAIN="go1.26.8", GOWORK="off", GOENV="off", GOFLAGS="", GOEXPERIMENT="", GOMAXPROCS="4")
rows = []
def run(key, command, extra=None):
    r = subprocess.run(command, cwd=module, env={**env, **(extra or {})}, capture_output=True, text=True, timeout=240)
    log = r.stdout + r.stderr
    (out / (key + ".txt")).write_text(log)
    row = {"key": key, "exit_code": r.returncode, "race_reports": log.count("WARNING: DATA RACE"),
           "log_sha256": hashlib.sha256(log.encode()).hexdigest(), "observations": [s for s in log.splitlines() if s.startswith("OBS ")]}
    rows.append(row)
    print(key, r.returncode, row["race_reports"], flush=True)
    return row
for backing in ("heap", "mmap"):
    for race in (False, True):
        cmd = ["go", "test", "-p", "1", "-count=1", "-v", *(["-race"] if race else [])]
        valid = run(backing + ("-race" if race else ""), [*cmd, "-run", "^Test(ValuesAndBounds|DisjointOrdinaryNeighbor|SameTargetAtomic|MixedSizeAtomic|SCStoreBuffering|SCIRIW|MixedWidthSC|Publication)$", "."], {"BACKING": backing})
        if valid["exit_code"]: raise RuntimeError("candidate contract failed")
        for name in ("OrdinaryTargetDiagnostic", "PlainPublicationDiagnostic", "RaceControl", "WideNeighborDiagnostic"):
            row = run(backing + "-" + name + ("-race" if race else ""), [*cmd, "-run", "^Test" + name + "$", "."], {"BACKING": backing})
            if not race and row["exit_code"]:raise RuntimeError("diagnostic failed to execute")
            if race and backing == "heap" and name in ("RaceControl", "WideNeighborDiagnostic", "PlainPublicationDiagnostic"):
                if not row["exit_code"] or not row["race_reports"]:raise RuntimeError("missing positive detector control")
assert run("native-vet", ["go", "vet", "."])["exit_code"] == 0
assert run("native-build", ["go", "test", "-c", "-o", str(out / "native.test"), "."])["exit_code"] == 0
assert run("linux-amd64-build", ["go", "test", "-c", "-o", str(out / "linux-amd64.test"), "."], {"GOOS": "linux", "GOARCH": "amd64", "CGO_ENABLED": "0"})["exit_code"] == 0
report = {"source_commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
          "source_templates": {s.name: hashlib.sha256(s.read_bytes()).hexdigest() for s in HERE.glob("*.txt")},
          "mapping_sha256": hashlib.sha256(mapping.read_bytes()).hexdigest(),
          "go": run("go-version", ["go", "version"]), "checks": rows,
          "scope": "Standalone exact-width candidate, not production adoption or general shared-memory proof"}
(out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
