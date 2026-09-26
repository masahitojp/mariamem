#!/usr/bin/env python3
"""Small local entry points for development, integration, release, and benchmarks."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = {
    "isolation": "isolation_baseline.py",
    "ready": "ready_to_query.py",
    "seeded": "seeded_database.py",
    "parallel": "parallel_databases.py",
    "memory": "memory_scaling.py",
}


def run(argv, *, env=None):
    print("+", " ".join(map(str, argv)), flush=True)
    subprocess.run([str(arg) for arg in argv], cwd=ROOT, env=env, check=True)


def check():
    run([sys.executable, "scripts/check_version.py"])
    run(["go", "test", "./..."])
    run(["go", "vet", "./..."])
    # Opt-in real-host pytest cases must stay skipped in the ordinary check,
    # even if a developer has a native bundle configured in their shell.
    env = os.environ.copy()
    env.pop("MARIAMEM_TEST_HOST", None)
    env.pop("MARIAMEM_NATIVE_DIR", None)
    env["PYTHONPATH"] = str(ROOT / "python")
    run([sys.executable, "-m", "pytest", "tests", "--ignore=tests/consumer", "-q"], env=env)
    run([sys.executable, "scripts/check_public.py"])


def integration():
    native = os.environ.get("MARIAMEM_NATIVE_DIR")
    if not native:
        raise SystemExit("integration requires MARIAMEM_NATIVE_DIR with a current native bundle")
    native = Path(native).expanduser().resolve()
    for name in ("manifest.json", "wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json"):
        if not (native / name).is_file():
            raise SystemExit(f"integration native bundle is missing {name}: {native}")
    env = os.environ.copy()
    env["MARIAMEM_NATIVE_DIR"] = str(native)
    env["PYTHONPATH"] = str(ROOT / "python")
    run(["go", "test", "-race", "-tags=integration", "./tests/gointegration",
         "-count=1", "-timeout=3m"], env=env)
    with tempfile.TemporaryDirectory(prefix="mariamem-integration-") as temporary:
        host = Path(temporary) / "mariamem-host"
        run(["go", "build", "-o", host, "./cmd/mariamem-host"], env=env)
        env["MARIAMEM_TEST_HOST"] = str(host)
        run([sys.executable, "-m", "pytest", "tests/test_python_timeout.py",
             "tests/test_python_multiclient.py", "-q"], env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="lightweight Go/Python/public-source checks")
    commands.add_parser("integration", help="real guest Go race and Python lifecycle checks")
    release = commands.add_parser("release-check", help="release guard; verify a local or CI candidate")
    release.add_argument("--ci-candidate-sha")
    release.add_argument("--native-acceptance")
    release.add_argument("--candidate-root", type=Path, help="exact CI candidate checkout")
    bench = commands.add_parser("bench", help="run one optional lifecycle benchmark")
    bench.add_argument("workload", choices=BENCHMARKS)
    args, extra = parser.parse_known_args()
    if args.command != "bench" and extra:
        parser.error("unexpected arguments: " + " ".join(extra))
    if args.command == "check":
        check()
    elif args.command == "integration":
        integration()
    elif args.command == "release-check":
        if bool(args.ci_candidate_sha) != bool(args.native_acceptance):
            parser.error("CI release check requires both --ci-candidate-sha and --native-acceptance")
        if args.ci_candidate_sha:
            command = [sys.executable, "scripts/check_ci_release.py", "--candidate-sha",
                       args.ci_candidate_sha, "--native-acceptance", args.native_acceptance]
            if args.candidate_root:
                command.extend(["--root", args.candidate_root])
            run(command)
        else:
            if args.candidate_root:
                parser.error("--candidate-root requires CI candidate/evidence arguments")
            run([sys.executable, "scripts/check_release.py"])
    else:
        run([sys.executable, ROOT / "benchmarks" / BENCHMARKS[args.workload], *extra])


if __name__ == "__main__":
    main()
