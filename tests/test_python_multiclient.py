"""Opt-in real-host smoke for Python clients sharing one database."""

import os
from pathlib import Path

import pytest

import mariamem
import pymysql


def test_two_python_clients_keep_independent_sessions():
    host = os.environ.get("MARIAMEM_TEST_HOST")
    native = os.environ.get("MARIAMEM_NATIVE_DIR")
    if not host or not native:
        pytest.skip("requires MARIAMEM_TEST_HOST and MARIAMEM_NATIVE_DIR")
    native = Path(native)
    with mariamem.start(host_binary=host, runtime=native / "wasmer-headless",
                        module=native / "mariamem.wasmu") as db:
        a = pymysql.connect(**db.connection_info(), autocommit=True)
        b = pymysql.connect(**db.connection_info(), autocommit=True)
        try:
            with a.cursor() as cur:
                cur.execute("SET @mariamem_test = 123")
                cur.execute("SELECT CONNECTION_ID()")
                a_id = cur.fetchone()[0]
            with b.cursor() as cur:
                cur.execute("SELECT CONNECTION_ID(), @mariamem_test")
                b_id, value = cur.fetchone()
                assert b_id != a_id and value is None
            a.close()
            with b.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone() == (1,)
        finally:
            if a.open:
                a.close()
            if b.open:
                b.close()
        db.wait_disconnected()
