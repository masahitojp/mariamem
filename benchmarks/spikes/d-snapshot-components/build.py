"""Build only the standalone spike, with isolated caches and recorded inputs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

here = Path(__file__).resolve().parent
root = here.parents[2]
workspace = root.parent
temp = workspace / "temp"
evidence = workspace / "evidence"
source = temp / "source"
source.mkdir(parents=True, exist_ok=True)
go = Path(os.environ["SPIKE_GO"])
env = os.environ.copy()
env.update(GOTOOLCHAIN="local", GO111MODULE="off", GOCACHE=str(temp / "gocache"), GOPATH=str(temp / "gopath"), TMPDIR=str(temp), GOTMPDIR=str(temp))
identity = json.loads(subprocess.check_output(["python3", "scripts/git_identity.py", "inspect", "HEAD"], cwd=root))
identity["toolchain"] = subprocess.check_output([str(go), "version"], env=env, text=True).strip()
identity["files_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in here.iterdir() if p.is_file()}
identity["source_worktree_modified"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root))
(evidence / "build-input.json").write_text(json.dumps(identity, indent=2)+"\n")
for name in ("main.go", "main_test.go"):
    shutil.copyfile(here / (name + ".txt"), source / name)
with (evidence / "build-tests.txt").open("w") as log:
    for command in ([str(go.parent / "gofmt"), "-w", "main.go", "main_test.go"],
                    [str(go), "test", "-v", "-count=1"],
                    [str(go), "build", "-o", str(temp / "component")]):
        subprocess.run(command, cwd=source, env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
identity["binary_sha256"] = hashlib.sha256((temp / "component").read_bytes()).hexdigest()
identity["formatted_source_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob("*.go")}
(evidence / "build-input.json").write_text(json.dumps(identity, indent=2)+"\n")
print("standalone model tests and build PASS", flush=True)
