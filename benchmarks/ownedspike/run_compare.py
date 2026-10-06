"""Bounded correctness-gated comparison orchestration, never a release benchmark."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-root", type=Path, required=True)
    p.add_argument("--baseline-bench", required=True)
    p.add_argument("--candidate-bench", required=True)
    p.add_argument("--baseline-host", required=True)
    p.add_argument("--candidate-host", required=True)
    p.add_argument("--helper", required=True)
    p.add_argument("--scratch", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--forks", type=int, default=16)
    p.add_argument("--correctness-passed", action="store_true", required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    a.scratch.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    variants = {"baseline": (a.baseline_bench, a.baseline_host, a.baseline_root / "python"),
                "candidate": (a.candidate_bench, a.candidate_host, root / "python")}
    for size in (0, 10, 100):
        external = a.scratch / f"external-{size}"
        for trial in range(a.trials):
            order = ("baseline", "candidate") if trial % 2 == 0 else ("candidate", "baseline")
            for label in order:
                print(f"Go size={size} trial={trial} {label}", flush=True)
                subprocess.run([variants[label][0], "-payload-mib", str(size), "-forks", str(a.forks),
                                "-helper", a.helper, "-label", label, "-out",
                                str(a.out / f"go-{size}-{trial}-{label}.json")], check=True)
        # A baseline-produced external artifact is the identical input to both
        # import paths. Provisioning itself is not counted as import cost.
        subprocess.run([a.baseline_bench, "-payload-mib", str(size), "-forks", "1",
                        "-export", str(external), "-label", "input-producer", "-out",
                        str(a.out / f"input-{size}.json")], check=True)
        manifest = json.loads((external / "manifest.json").read_text())
        (a.out / f"manifest-{size}.json").write_text(json.dumps(manifest, indent=2) + "\n")
        for trial in range(a.trials):
            order = ("baseline", "candidate") if trial % 2 == 0 else ("candidate", "baseline")
            for label in order:
                print(f"Python import size={size} trial={trial} {label}", flush=True)
                env = dict(os.environ, PYTHONPATH=str(variants[label][2]))
                subprocess.run([sys.executable, str(Path(__file__).with_name("import_measure.py")),
                                "--artifact", str(external), "--host", variants[label][1],
                                "--label", label, "--helper", a.helper, "--forks", str(a.forks),
                                "--out", str(a.out / f"import-{size}-{trial}-{label}.json")],
                               check=True, env=env)
        shutil.rmtree(external)


if __name__ == "__main__":
    main()
