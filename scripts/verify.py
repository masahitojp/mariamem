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
    "envelope": "memory_envelope.py",
    "competitive": "testcontainers_compare.py",
    "go-isolation": "go_isolation.py",
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
    run([sys.executable, "scripts/verify_generated_runtime.py"])
    run(["go", "test", "-p", "1", "./..."])
    # wasm2go emits dead structured-control fallthrough. Retain every other
    # analyzer there; handwritten runtime/shim/API packages retain full vet.
    tool_dir = subprocess.check_output(["go", "env", "GOTOOLDIR"], cwd=ROOT, text=True).strip()
    env = dict(os.environ, MARIAMEM_VET_TOOL=str(Path(tool_dir)/"vet"))
    run(["go", "vet", "-p", "1", "-vettool="+str(ROOT/"scripts/vet_generated.py"), "./..."], env=env)
    # Opt-in real-host pytest cases must stay skipped in the ordinary check,
    # even if a developer has a native bundle configured in their shell.
    env = os.environ.copy()
    env.pop("MARIAMEM_TEST_HOST", None)
    env.pop("MARIAMEM_NATIVE_DIR", None)
    env["PYTHONPATH"] = str(ROOT / "python")
    run([sys.executable, "-m", "pytest", "tests", "--ignore=tests/consumer", "--ignore=tests/historical", "-q"], env=env)
    run([sys.executable, "scripts/check_public.py"])


def integration():
    env = os.environ.copy()
    env.pop("MARIAMEM_NATIVE_DIR", None)
    env.pop("MARIAMEM_RUNTIME", None)
    env["MARIAMEM_TEST_DEFAULT"] = "1"
    env["PYTHONPATH"] = str(ROOT / "python")
    # v0.4 keeps handwritten/runtime race coverage. Full generated guest races
    # are a documented shared-memory-model limitation, not a release gate.
    run(["go", "test", "-race", "-p", "1", "./internal/generatedgo/code/base",
         "./internal/generatedgo", "./internal/guest", "./internal/host",
         "./internal/mysqlwire", "./internal/snapshot", "-count=1"], env=env)
    command = ["go", "test"]
    run([*command, "-tags=integration", "./tests/gointegration",
         "-count=1", "-timeout=3m"], env=env)
    # These tests deliberately clear native overrides and execute the full guest.
    run(["go", "test", "-tags=integration", "./tests/godefault",
         "-count=1", "-timeout=3m"], env=env)
    # Guest OOB failures must trap without terminating the host process.
    run(["go", "test", "-p", "1", "-tags=integration", "./tests/generatedmemory",
         "-count=1", "-timeout=3m"], env=env)
    with tempfile.TemporaryDirectory(prefix="mariamem-integration-") as temporary:
        host = Path(temporary) / "mariamem-host"
        run(["go", "build", "-p", "1", "-o", host, "./cmd/mariamem-host"], env=env)
        env["MARIAMEM_TEST_HOST"] = str(host)
        timeout_test = "tests/test_python_timeout.py::test_normal_close_is_idempotent"
        print("Forced query-timeout reclamation remains a separate diagnostic; "
              "normal Close remains required.", flush=True)
        run([sys.executable, "-m", "pytest", timeout_test,
             "tests/test_python_multiclient.py", "tests/test_owned_snapshot.py", "-q"], env=env)
        run([sys.executable, "tests/snapshots.py"], env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="lightweight Go/Python/public-source checks")
    commands.add_parser("integration", help="normal guest acceptance, focused runtime race and Python lifecycle checks")
    release = commands.add_parser("release-check", help="release guard; verify a local or CI candidate")
    release.add_argument("--ci-candidate-sha")
    release.add_argument("--platform", choices=("darwin-arm64", "ubuntu24.04-x86_64"))
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
        if args.ci_candidate_sha:
            command = [sys.executable, "scripts/release_generated_ci.py", "guard",
                       "--candidate-sha", args.ci_candidate_sha]
            if args.candidate_root:
                command.extend(["--root", args.candidate_root])
            if args.platform:
                command.extend(["--platform", args.platform])
            run(command)
        else:
            if args.candidate_root or args.platform:
                parser.error("candidate root/platform requires --ci-candidate-sha")
            run([sys.executable, "scripts/check_release.py"])
    else:
        run([sys.executable, ROOT / "benchmarks" / BENCHMARKS[args.workload], *extra])


if __name__ == "__main__":
    main()
