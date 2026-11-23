"""Shared installed-wheel acceptance on native macOS and Windows."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import mariamem
import pymysql
import pytest

from test_database import execute


def test_parallel_fork_isolation():
    both_written = Barrier(2, timeout=30)
    with mariamem.start() as db:
        execute(db.connection_info(), "CREATE TABLE native_fork (id INT PRIMARY KEY)")
        db.wait_disconnected()
        with db.snapshot(max_forks=2) as snapshot:
            def write_and_read(value):
                with snapshot.fork(timeout=30) as child:
                    info = child.connection_info()
                    execute(info, f"INSERT INTO native_fork VALUES ({value})")
                    both_written.wait()
                    return execute(info, "SELECT id FROM native_fork")

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(write_and_read, value) for value in (1, 2)]
                assert [future.result(timeout=60) for future in futures] == [((1,),), ((2,),)]


def test_host_failure_is_reaped():
    db = mariamem.start()
    session = db._session
    try:
        with pymysql.connect(**db.connection_info(), read_timeout=5, write_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                assert cursor.fetchone() == (1,)
                session._process.kill()
                session._process.wait(timeout=5)
                with pytest.raises(pymysql.MySQLError):
                    cursor.execute("SELECT 1")
            with pytest.raises(mariamem.HostError):
                db.status()
    finally:
        db.close()
    assert session._process.poll() is not None
    assert not session.root.exists()
