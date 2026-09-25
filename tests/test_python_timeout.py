"""Opt-in real-host check for the Python wrapper's fatal query-timeout state."""

import os
from pathlib import Path
import time

import pytest

import mariamem
import pymysql


def test_normal_close_is_idempotent():
    host = os.environ.get("MARIAMEM_TEST_HOST")
    native = os.environ.get("MARIAMEM_NATIVE_DIR")
    if not host or not native:
        pytest.skip("requires MARIAMEM_TEST_HOST and MARIAMEM_NATIVE_DIR")
    native = Path(native)
    db = mariamem.start(host_binary=host, runtime=native / "wasmer-headless",
                        module=native / "mariamem.wasmu")
    temporary = db.log_path.parent
    assert db.status()["state"] == "ready"
    db.close()
    db.close()
    assert db.closed and not temporary.exists()


def test_query_timeout_disposes_wrapper():
    host = os.environ.get("MARIAMEM_TEST_HOST")
    native = os.environ.get("MARIAMEM_NATIVE_DIR")
    if not host or not native:
        pytest.skip("requires MARIAMEM_TEST_HOST and MARIAMEM_NATIVE_DIR")
    native = Path(native)
    db = mariamem.start(host_binary=host, runtime=native / "wasmer-headless",
                        module=native / "mariamem.wasmu", query_timeout=1)
    runtime_pid = db.diagnostics["runtime_pid"]
    temporary = db.log_path.parent
    try:
        with pymysql.connect(**db.connection_info(), read_timeout=5) as conn:
            with conn.cursor() as cursor:
                # The guest query outlives the one-second host deadline.
                with pytest.raises(pymysql.Error, match="database instance terminated"):
                    cursor.execute("SELECT SLEEP(10)")
        deadline = time.monotonic() + 5
        while not db.closed and time.monotonic() < deadline:
            time.sleep(0.01)
        assert db.closed
        with pytest.raises(mariamem.HostError) as failure:
            db.status()
        assert failure.value.code == "unusable" and failure.value.closed
    finally:
        db.close()
        db.close()
    assert not temporary.exists()
    with pytest.raises(ProcessLookupError):
        os.kill(runtime_pid, 0)
