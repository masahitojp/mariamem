"""Run in a disposable Linux builder image; no guest build or SDK installation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
workflow = (ROOT / ".github/workflows/routine-bootstrap.yml").read_text()
for name in ("Trust only this container checkout for Git identity checks",
             "Exact source, fresh SDK, normal development guest route"):
    assert f"- name: {name}\n        env:\n          HOME: /root\n" in workflow
source = HERE / "wasix-toolchain.cmake"
pins = json.loads((ROOT / "guest/input.json").read_text())
expected = "114c296e33df8bb68bab6797d1b40b11834a2c3cfe1e934ffbe87037816c32ea"
assert expected in json.dumps(pins)
assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
with tempfile.TemporaryDirectory(prefix="routine-sdk-home-") as directory:
    base = Path(directory)
    probe = base / "probe.cmake"
    probe.write_text('include("' + str(source) + '")\n'
                     'if(NOT EXISTS "${CMAKE_C_COMPILER}")\n'
                     '  message(FATAL_ERROR "SDK compiler missing: ${CMAKE_C_COMPILER}")\n'
                     'endif()\n'
                     'message(STATUS "SDK compiler found: ${CMAKE_C_COMPILER}")\n')
    results = {}
    for label, home in (("ci_default", "/github/home"), ("fixed_builder", "/root")):
        env = {**os.environ, "HOME": home}
        result = subprocess.run(["cmake", "-P", str(probe)], env=env,
                                text=True, capture_output=True)
        results[label] = {"home": home, "returncode": result.returncode,
                          "stdout": result.stdout, "stderr": result.stderr}
    assert results["ci_default"]["returncode"] != 0
    assert "/github/home/.wasixcc/bin/wasixcc" in results["ci_default"]["stderr"]
    assert results["fixed_builder"]["returncode"] == 0
    assert "/root/.wasixcc/bin/wasixcc" in results["fixed_builder"]["stdout"]
    # The trust step and nested source inspection must share the same config HOME.
    checkout = base / "checkout"
    checkout.mkdir()
    env = {**os.environ, "HOME": "/root", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", str(checkout)], env=env, check=True, capture_output=True)
    subprocess.run(["git", "config", "--global", "--add", "safe.directory", str(checkout)],
                   env=env, check=True)
    result = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain"],
                            env={**env, "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"},
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    results["shared_home_git_identity"] = "PASS"
    results["source_sha256"] = expected
    results["result"] = "PASS (path/config probe only; not a guest build)"
    print(json.dumps(results, indent=2))
