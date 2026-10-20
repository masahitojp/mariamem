"""Reproduce container Git ownership rejection without changing global config."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
workflow = (ROOT / ".github/workflows/routine-bootstrap.yml").read_text()
line = 'git config --global --add safe.directory "$GITHUB_WORKSPACE"'
assert workflow.count(line) == 1
assert workflow.index(line) < workflow.index("python3 scripts/git_identity.py inspect HEAD")
with tempfile.TemporaryDirectory(prefix="routine-ci-owner-") as directory:
    base = Path(directory)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": str(base / "gitconfig"),
           "GIT_CONFIG_NOSYSTEM": "1"}
    def git(path, *args, check=True, owner=False):
        active = {**env, "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"} if owner else env
        return subprocess.run(["git", "-C", str(path), *args], env=active,
                              text=True, capture_output=True, check=check)
    checkout = base / "checkout"
    other = base / "other"
    checkout.mkdir()
    other.mkdir()
    git(checkout, "init")
    git(other, "init")
    before = git(checkout, "status", "--porcelain", check=False, owner=True)
    assert before.returncode != 0 and "dubious ownership" in before.stderr
    # Execute exactly the workflow command, with a disposable global config.
    subprocess.run(line, shell=True, check=True,
                   env={**env, "GITHUB_WORKSPACE": str(checkout)})
    after = git(checkout, "status", "--porcelain", owner=True)
    assert after.stdout == ""
    rejected = git(other, "status", "--porcelain", check=False, owner=True)
    assert rejected.returncode != 0 and "dubious ownership" in rejected.stderr
    values = git(checkout, "config", "--global", "--get-all", "safe.directory")
    assert values.stdout.splitlines() == [str(checkout)]
    print(json.dumps({"before": "ownership rejection reproduced",
                      "after": "exact checkout accepted",
                      "other_repository": "still rejected",
                      "workflow_order": "trust precedes identity check",
                      "result": "PASS"}, indent=2))
