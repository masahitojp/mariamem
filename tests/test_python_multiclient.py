"""Opt-in real-host smoke for Python clients sharing one database."""

import os
from pathlib import Path

import pytest

import mariamem
import pymysql


def test_two_python_clients_keep_independent_sessions():
    host = os.environ.get("MARIAMEM_TEST_HOST")
    if not host or os.environ.get("MARIAMEM_TEST_DEFAULT") != "1":
        pytest.skip("requires generated-Go MARIAMEM_TEST_HOST and MARIAMEM_TEST_DEFAULT=1")
    options = {"host_binary":host}
    with mariamem.start(**options) as db:
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
