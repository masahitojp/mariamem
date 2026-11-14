"""Run candidate-specific actual guest controls on canonical CI source.

Test-only overlays inject EIO and observe real redo recovery. They never enter
product code or performance binaries. Output is an external disposable directory.
The archived measurement harness remains immutable.
"""
from layout import BENCHMARKS, FIXTURES

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPOSITORY = Path(__file__).resolve().parents[1]
ARCHIVE = REPOSITORY / (BENCHMARKS / 'forkcost/buffer-zero-candidate')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    evidence = out / "evidence"
    temp = out / "temp"
    evidence.mkdir()
    temp.mkdir()
    (temp / "tmp").mkdir()

    # Reuse the archived overlay recipe with an explicit canonical source root.
    recipe = (ARCHIVE / "tools/build-extra.py").read_text()
    original = "product=X/'worktree' if variant=='baseline' else T/'native/product'"
    assert original in recipe
    recipe = recipe.replace(
        original, 'product=Path(os.environ["MARIAMEM_BUFFER_CANDIDATE_ROOT"])'
    ).replace("GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),", "")
    builder = evidence / "build-extra.py"
    builder.write_text(recipe)

    for name in ("correct", "fault", "recovery"):
        shutil.copytree(ARCHIVE / "harness" / name, temp / name)
        module = temp / name / "go.mod"
        text = re.sub(r"(?m)^go 1\.27$", "go 1.26.0", module.read_text())
        module.write_text(
            text[:text.index("replace github.com/masahitojp/mariamem")]
            + f"replace github.com/masahitojp/mariamem => {root}\n"
        )
    fault_source = root / (FIXTURES / 'buffer-pool-fault/main.go.txt')
    shutil.copy2(fault_source, temp / "fault/main.go")
    for name in ("buffer_fault_experiment.go", "buffer_recovery_witness.go"):
        shutil.copy2(ARCHIVE / "harness" / (name + ".txt"), temp / name)
    env = dict(
        os.environ,
        MARIAMEM_BUFFER_CANDIDATE_ROOT=str(root),
        CGO_ENABLED="0",
        GOMAXPROCS="8",
        GOGC="100",
        TMPDIR=str(temp / "tmp"),
    )

    def run(name, command):
        with (evidence / (name + ".log")).open("w") as log:
            subprocess.run(
                command, env=env, stdout=log, stderr=subprocess.STDOUT,
                check=True, timeout=1200,
            )
        print("PASS", name, flush=True)

    run("build", [sys.executable, str(builder), "candidate"])
    for name, binary, flags in (
        ("basic", "correct", ["-case", "basic"]),
        ("large", "correct", ["-case", "large"]),
        ("fault", "fault", []),
        ("recovery-clean", "recovery", ["-crash=false"]),
        ("recovery-dirty", "recovery", ["-crash=true"]),
    ):
        result = evidence / (name + ".json")
        run(name, [str(temp / ("candidate-" + binary)), *flags, "-out", str(result)])
        assert json.loads(result.read_text())["success"]
    (evidence / "result.json").write_text(json.dumps({
        "result": "PASS",
        "guest_sha256": json.loads(
            (root / "release/generated-go-inputs.json").read_text()
        )["guest_sha256"],
        "fault_fixture_sha256": hashlib.sha256(fault_source.read_bytes()).hexdigest(),
        "fault_arming": (
            "ibd after Ready; 32MiB full CRC exceeds 16MiB pool; ibdata1 before Fork"
        ),
        "scope": (
            "canonical actual basic/large/compressed/resize/Fork/fault/clean-vs-dirty "
            "redo controls; test-only overlays excluded from product"
        ),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
