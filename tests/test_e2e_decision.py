"""The Human-required probe record precedes product entry code."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISION_COMMIT = "3ead1bc8d1ebb984f912cf4062c7a6dd759698c9"

def test_e2e_implementation_has_precode_decision():
    subprocess.run(["git", "merge-base", "--is-ancestor", DECISION_COMMIT, "HEAD"], cwd=ROOT, check=True)
    record = subprocess.check_output(["git", "show", DECISION_COMMIT + ":docs/decisions/e2e-entry-implementation.md"], cwd=ROOT, text=True)
    for value in ("03b90c17f558d6ab3f9d0f376fa50db9435261fb", "870af0ab793b7adc48c11f3e39108416dce0b330", "Human approved", "not actual Live/app/browser", "readable-owned"):
        assert value in record
    for path in ("python/mariamem/e2e.py", "mariamemtest/http.go"):
        result = subprocess.run(["git", "cat-file", "-e", DECISION_COMMIT + ":" + path], cwd=ROOT, stderr=subprocess.DEVNULL)
        assert result.returncode != 0, "decision must precede product code"
