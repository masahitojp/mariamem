#!/usr/bin/env python3
"""Installed-wheel acceptance outside the repository, with no native overrides."""
import importlib.metadata
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import mariamem

ROOT = Path(__file__).resolve().parents[1]
(ROOT / "tests/evidence").mkdir(parents=True, exist_ok=True)
wheel_record = json.loads((ROOT / "tests/evidence/alpha-wheel.json").read_text())
wheel_path = ROOT / wheel_record["wheel"]
assert hashlib.sha256(wheel_path.read_bytes()).hexdigest() == wheel_record["sha256"]
with zipfile.ZipFile(wheel_path) as archive:
    for name in archive.namelist():
        if "/mariamem/" in name:
            relative = name.split("/mariamem/", 1)[1]
            installed = Path(mariamem.__file__).parent / relative
            assert installed.read_bytes() == archive.read(name), f"installed wheel mismatch: {relative}"
report = {"version": importlib.metadata.version("mariamem"), "runs": [],
          "wheel_sha256": wheel_record["sha256"], "installed_files_match_wheel": True}
audit_plugin = '''import json
import os
from pathlib import Path
import mariamem

def pytest_fixture_post_finalizer(fixturedef, request):
    cached = fixturedef.cached_result
    if cached is None or cached[2] is not None:
        return
    value = cached[0]
    if isinstance(value, mariamem.Database):
        assert value.closed
        assert not value.log_path.parent.exists()
        for pid in value.diagnostics.values():
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            else:
                raise AssertionError(f"process {pid} survived teardown")
        record = {"fixture": fixturedef.argname, "id": value.id, "reaped": True}
        (Path(os.environ["ALPHA_AUDIT"]) / (value.id + ".json")).write_text(json.dumps(record))
    elif isinstance(value, mariamem.Snapshot):
        assert not value.path.exists()
'''


def main():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("MARIAMEM_", "MYSQLMEM_", "PYTHON", "PYTEST"))}
    env["PATH"] = "/usr/bin:/bin"
    with tempfile.TemporaryDirectory(prefix="mariamem-consumer-") as temporary:
        project = Path(temporary)
        shutil.copy(ROOT / "tests/consumer/test_database.py", project)
        (project / "audit_plugin.py").write_text(audit_plugin)

        def run(name, arguments, failures=0, errors=0):
            audit = project / (name + "-audit")
            audit.mkdir()
            junit = project / (name + ".xml")
            result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=short",
                                     "-p", "audit_plugin", "--junitxml", str(junit), *arguments],
                                    cwd=project, env=dict(env, ALPHA_AUDIT=str(audit)),
                                    capture_output=True, text=True, timeout=300)
            (ROOT / "tests/evidence" / ("alpha-" + name + ".log")).write_text(result.stdout + result.stderr)
            assert result.returncode == (1 if failures or errors else 0), result.stdout + result.stderr
            suites = list(ET.parse(junit).getroot().iter("testsuite"))
            counts = {key: sum(int(s.get(key, 0)) for s in suites)
                      for key in ("tests", "failures", "errors", "skipped")}
            assert counts["failures"] == failures and counts["errors"] == errors, counts
            records = [json.loads(p.read_text()) for p in audit.glob("*.json")]
            assert records and all(r["reaped"] for r in records)
            report["runs"].append({"name": name, **counts, "fixture_instances_reaped": len(records)})
            print(json.dumps(report["runs"][-1]), flush=True)

        run("serial", ["test_database.py"])
        run("parallel", ["-n", "2", "--dist=loadscope", "test_database.py"])
        (project / "conftest.py").write_text('''import pytest
from test_database import execute

@pytest.fixture(scope="session")
def mariamem_snapshot(mariamem_server):
    execute(mariamem_server.connection_info(), "CREATE TABLE seed(id INT) ENGINE=InnoDB")
    mariamem_server.wait_disconnected()
    execute(mariamem_server.connection_info(), "INSERT INTO seed VALUES(42)")
    mariamem_server.wait_disconnected()
    with mariamem_server.snapshot() as saved:
        yield saved
''')
        (project / "test_seed.py").write_text('''import pytest
from test_database import execute

@pytest.mark.parametrize("number", [1, 2])
def test_seed(mariamem_connection_info, number):
    assert execute(mariamem_connection_info, "SELECT id FROM seed") == ((42,),)
''')
        run("migration", ["test_seed.py"])
        (project / "test_failure.py").write_text('''import pytest
import pymysql

def test_assertion(mariamem_connection_info):
    with pymysql.connect(**mariamem_connection_info) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO seed VALUES(99)")
            assert False, "intentional failure with uncommitted transaction"

@pytest.fixture
def broken(mariamem_fork):
    raise RuntimeError("intentional setup error")

def test_setup(broken):
    pass
''')
        run("failure-cleanup", ["test_failure.py"], failures=1, errors=1)
        report["passed"] = True
        report["runtime_bundled_in_wheel"] = True
        report["native_overrides"] = False
        report["consumer_outside_repository"] = True


if __name__ == "__main__":
    try:
        main()
    finally:
        report.setdefault("passed", False)
        (ROOT / "tests/evidence/alpha.json").write_text(json.dumps(report, indent=2) + "\n")
