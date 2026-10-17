"""Bounded real-host acceptance for the owned-template production contract."""
from concurrent.futures import ThreadPoolExecutor
import errno
import gc
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import threading
import time

import mariamem
import pymysql
import pytest

HOST = os.environ.get("MARIAMEM_TEST_HOST")
pytestmark = pytest.mark.skipif(not HOST, reason="requires explicit real host")


def fd_count():
    if Path("/proc/self/fd").is_dir():
        return len(os.listdir("/proc/self/fd"))
    import fcntl
    count = 0
    for fd in range(resource.getrlimit(resource.RLIMIT_NOFILE)[0]):
        try:
            fcntl.fcntl(fd, fcntl.F_GETFD)
            count += 1
        except OSError as error:
            if error.errno != errno.EBADF:
                raise
    return count


def host_fd_count(pid):
    directory = Path(f"/proc/{pid}/fd")
    if directory.is_dir():
        return len(list(directory.iterdir()))
    # Numeric descriptor fields only: exclude cwd, executable and memory maps.
    text = subprocess.check_output(["/usr/sbin/lsof", "-a", "-p", str(pid), "-Ff"], text=True)
    return sum(line.startswith("f") and line[1:].isdigit() for line in text.splitlines())


def sql(db, statement, args=None):
    with pymysql.connect(**db.connection_info(), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement, args)
            return cursor.fetchall()


def initial(db):
    assert sql(db, "SELECT id,label,OCTET_LENGTH(payload) FROM owned_items ORDER BY id") == (
        (1, "seed", 1024), (2, "seed", 1024), (3, "seed", 1024))
    assert sql(db, "SHOW COLUMNS FROM owned_items")[0][0] == "id"
    assert len(sql(db, "SHOW COLUMNS FROM owned_items")) == 3
    assert sql(db, "SHOW TABLES LIKE 'child_only'") == ()


def mutate(db, kind):
    initial(db)
    if kind == 0:
        # Exceeds initial table capacity: 8 MiB private growth.
        with pymysql.connect(**db.connection_info(), autocommit=True) as connection:
            with connection.cursor() as cursor:
                for first in range(100, 2148, 128):
                    cursor.executemany("INSERT INTO owned_items VALUES(%s,'child',%s)",
                                       [(i, b"x" * 4096) for i in range(first, first + 128)])
        assert sql(db, "SELECT COUNT(*) FROM owned_items") == ((2051,),)
    elif kind == 1:
        with pymysql.connect(**db.connection_info()) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE owned_items SET label='rollback' WHERE id=1")
                cursor.execute("DELETE FROM owned_items WHERE id=2")
                connection.rollback()
                cursor.execute("SELECT COUNT(*) FROM owned_items")
                assert cursor.fetchone() == (3,)
                cursor.execute("UPDATE owned_items SET label='commit' WHERE id=1")
                cursor.execute("DELETE FROM owned_items WHERE id=2")
                connection.commit()
        assert sql(db, "SELECT id,label FROM owned_items ORDER BY id") == ((1, "commit"), (3, "seed"))
    else:
        sql(db, "ALTER TABLE owned_items ADD COLUMN child INT DEFAULT 7")
        sql(db, "CREATE TABLE child_only(id INT) ENGINE=InnoDB")
        sql(db, "DROP TABLE child_only")
        assert sql(db, "SELECT child FROM owned_items WHERE id=1") == ((7,),)


def prepared():
    with mariamem.start(host_binary=HOST) as source:
        sql(source, "CREATE TABLE owned_items(id INT PRIMARY KEY,label VARCHAR(32),payload LONGBLOB) ENGINE=InnoDB")
        sql(source, "INSERT INTO owned_items VALUES(1,'seed',REPEAT('a',1024)),(2,'seed',REPEAT('b',1024)),(3,'seed',REPEAT('c',1024))")
        source.wait_disconnected()
        return source.snapshot()


def test_many_order_and_parallel_siblings():
    before_fd, before_threads = fd_count(), threading.active_count()
    with prepared() as saved:
        session = saved._session
        def work(kind):
            with saved.fork() as db:
                assert db.diagnostics["host_pid"] == session._process.pid
                mutate(db, kind)
        for kind in [0, 1, 2, 2, 0, 1, 1, 2, 0, *[i % 3 for i in range(10)]]:
            work(kind)
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(work, [i % 3 for i in range(16)]))
        with saved.fork() as child:
            saved.close()
            saved.close()
            initial(child)
        with pytest.raises(ValueError, match="closed"):
            saved.fork()
    gc.collect()
    assert fd_count() == before_fd
    assert threading.active_count() == before_threads
    assert session._process.poll() == 0
    assert not session.root.exists()


def test_modified_child_creates_new_baseline_without_changing_parent():
    before = fd_count()
    with prepared() as parent:
        with parent.fork() as child:
            mutate(child, 1)
            child.wait_disconnected()
            with child.snapshot() as derived:
                assert child.closed
                with derived.fork() as changed:
                    assert sql(changed, "SELECT id,label FROM owned_items ORDER BY id") == ((1, "commit"), (3, "seed"))
                with parent.fork() as unchanged:
                    initial(unchanged)
                parent.close()
                with derived.fork() as surviving:
                    assert sql(surviving, "SELECT id,label FROM owned_items ORDER BY id") == ((1, "commit"), (3, "seed"))
    assert fd_count() == before


def test_hundred_forks_and_ten_generations():
    before = fd_count()
    with prepared() as original:
        session = original._session
        host_fds = host_fd_count(session._process.pid)
        scratch = {p.relative_to(session.root) for p in session.root.rglob("*")}
        for _ in range(100):
            with original.fork() as child:
                initial(child)
        assert host_fd_count(session._process.pid) == host_fds
        assert {p.relative_to(session.root) for p in session.root.rglob("*")} == scratch
        parent = original
        derived = []
        try:
            for generation in range(10):
                with parent.fork() as child:
                    initial(child)
                    child.wait_disconnected()
                    parent = child.snapshot()
                    derived.append(parent)
            original.close()
            for old in derived[:-1]:
                old.close()
            with parent.fork() as last:
                initial(last)
        finally:
            for item in reversed(derived):
                item.close()
    assert fd_count() == before
    assert session._process.poll() == 0


def test_host_kill_loses_one_lineage_and_reaps_owned_directories():
    import signal
    with mariamem.start(host_binary=HOST) as independent:
        baseline = prepared()
        a, b = baseline.fork(), baseline.fork()
        session = baseline._session
        try:
            with pymysql.connect(**a.connection_info()) as connection, ThreadPoolExecutor(1) as workers:
                assert a.status()["active_connections"] == 1
                entered = threading.Event()
                original = a.status
                def observed_status():
                    value = original()
                    entered.set()
                    return value
                a.status = observed_status
                wait = workers.submit(a.wait_disconnected, 10)
                assert entered.wait(5) and not wait.done()
                # Host termination is deliberately process-wide, never an
                # assertion that one arbitrary guest can be forcibly reclaimed.
                os.kill(session._process.pid, signal.SIGKILL)
                with pytest.raises(mariamem.HostError):
                    wait.result(5)
            with pytest.raises(mariamem.HostError):
                baseline.fork()
            with pytest.raises(mariamem.HostError):
                b.status()
            assert sql(independent, "SELECT 1") == ((1,),)
        finally:
            a.close(); b.close(); baseline.close()
        assert session._process.poll() is not None
        assert not session.root.exists()


def test_explicit_other_binary_uses_private_handoff(tmp_path):
    binary = tmp_path / "alternate-host"
    shutil.copy2(HOST, binary)
    binary.chmod(0o755)
    with prepared() as baseline:
        with baseline.fork(host_binary=binary) as other:
            assert other.diagnostics["host_pid"] != baseline._session._process.pid
            initial(other)
            mutate(other, 1)
        with baseline.fork() as unchanged:
            initial(unchanged)
        assert not list(baseline._session.root.glob("handoff-*"))


def test_wait_on_one_database_does_not_delay_sibling_close():
    with prepared() as baseline:
        with baseline.fork() as waiting, baseline.fork() as sibling:
            connection = pymysql.connect(**waiting.connection_info())
            try:
                with ThreadPoolExecutor(2) as pool:
                    assert waiting.status()["active_connections"] == 1
                    pending = pool.submit(waiting.wait_disconnected, 10)
                    pool.submit(sibling.close).result(5)
                    assert not pending.done()
                    connection.close()
                    pending.result(5)
            finally:
                if connection.open:
                    connection.close()
            initial(waiting)


def test_real_fork_racing_baseline_close_preserves_started_children():
    baseline = prepared()
    session = baseline._session
    first = baseline.fork()
    gate = threading.Barrier(5)
    def fork():
        gate.wait()
        try:
            return baseline.fork()
        except (mariamem.HostError, ValueError) as error:
            assert "closed" in str(error).lower()
            return None
    with ThreadPoolExecutor(4) as pool:
        pending = [pool.submit(fork) for _ in range(4)]
        gate.wait()
        baseline.close()
        children = [first]
        try:
            initial(first)
            for future in pending:
                child = future.result(20)
                if child is not None:
                    children.append(child)
                    initial(child)
        finally:
            for child in children:
                child.close()
    assert session._process.poll() == 0
    assert not session.root.exists()


def test_mapped_child_resnapshot_preserves_independent_lineage(tmp_path):
    """A private handoff's mapping must not outlive its child via a new baseline."""
    alternate = tmp_path / "alternate-host"
    shutil.copy2(HOST, alternate)
    alternate.chmod(0o755)
    with mariamem.start(host_binary=HOST) as source:
        sql(source, "CREATE TABLE mapped_lineage(id INT PRIMARY KEY,value INT) ENGINE=InnoDB")
        sql(source, "INSERT INTO mapped_lineage VALUES(1,10)")
        source.wait_disconnected()
        with source.snapshot() as baseline:
            with baseline.fork(host_binary=alternate) as mapped:
                sql(mapped, "UPDATE mapped_lineage SET value=20 WHERE id=1")
                mapped.wait_disconnected()
                with mapped.snapshot() as derived:
                    with derived.fork() as child:
                        assert sql(child, "SELECT value FROM mapped_lineage WHERE id=1") == ((20,),)
                        sql(child, "UPDATE mapped_lineage SET value=30 WHERE id=1")
                    with derived.fork() as sibling:
                        assert sql(sibling, "SELECT value FROM mapped_lineage WHERE id=1") == ((20,),)
            with baseline.fork() as untouched:
                assert sql(untouched, "SELECT value FROM mapped_lineage WHERE id=1") == ((10,),)
            assert not list(baseline._session.root.glob("handoff-*"))
