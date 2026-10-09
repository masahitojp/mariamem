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


@pytest.fixture(scope="module")
def artifact(tmp_path_factory):
    path = tmp_path_factory.mktemp("owned-input") / "snapshot"
    with mariamem.start(host_binary=HOST) as db:
        sql(db, "CREATE TABLE owned_items(id INT PRIMARY KEY,label VARCHAR(32),payload LONGBLOB) ENGINE=InnoDB")
        sql(db, "INSERT INTO owned_items VALUES(1,'seed',REPEAT('a',1024)),(2,'seed',REPEAT('b',1024)),(3,'seed',REPEAT('c',1024))")
        db.wait_disconnected()
        with db.snapshot_to(path):
            pass
    return path


@pytest.mark.parametrize("damage", ["content", "missing", "extra", "truncate", "guest", "format", "bool-version", "float-version", "float-size", "symlink"])
def test_import_rejects_at_boundary(artifact, tmp_path, damage):
    path = tmp_path / "input"
    shutil.copytree(artifact, path)
    victim = next(p for p in (path / "data").rglob("*") if p.is_file() and p.stat().st_size)
    if damage == "content":
        with victim.open("r+b") as file:
            file.write(b"CORRUPT")
    elif damage == "missing":
        victim.unlink()
    elif damage == "extra":
        (path / "data/extra").write_bytes(b"extra")
    elif damage == "truncate":
        victim.write_bytes(b"")
    elif damage in ("guest", "format", "bool-version", "float-version", "float-size"):
        manifest = json.loads((path / "manifest.json").read_text())
        if damage == "float-size":
            entry = next(v for v in manifest["entries"].values() if v["kind"] == "file")
            entry["bytes"] = float(entry["bytes"])
        else:
            key = "wasm_sha256" if damage == "guest" else "version"
            manifest[key] = {"guest": "f" * 64, "format": 999, "bool-version": True, "float-version": 1.0}[damage]
        (path / "manifest.json").write_text(json.dumps(manifest))
    else:
        victim.unlink()
        victim.symlink_to(artifact / "manifest.json")
    before = fd_count()
    with pytest.raises(ValueError):
        mariamem.load_snapshot(path, host_binary=HOST)
    assert fd_count() == before


def test_import_owns_exact_resource_and_original_disappears(artifact, tmp_path):
    path = tmp_path / "input"
    shutil.copytree(artifact, path)
    with mariamem.load_snapshot(path, host_binary=HOST) as saved:
        for name, fd, size in saved._files:
            owned, external = os.fstat(fd), (path / "data" / name).stat()
            assert owned.st_nlink == 0 and owned.st_size == size
            assert (owned.st_dev, owned.st_ino) != (external.st_dev, external.st_ino)
            with pytest.raises(OSError) as error:
                os.pwrite(fd, b"mutation", 0)
            assert error.value.errno == errno.EBADF
        shutil.rmtree(path)
        path.mkdir()
        (path / "replacement").write_bytes(b"unrelated")
        with saved.fork() as db:
            initial(db)
        shutil.rmtree(path)
        with saved.fork() as db:
            initial(db)


def test_many_order_and_parallel_siblings(artifact):
    before_fd, before_threads = fd_count(), threading.active_count()
    pids = []
    with mariamem.load_snapshot(artifact, host_binary=HOST) as saved:
        def work(kind):
            with saved.fork() as db:
                pids.append(db.diagnostics["host_pid"])
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
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    print(f"Python: 35 mutating children, 4 workers, FD {before_fd}->{fd_count()}, threads {before_threads}->{threading.active_count()}, all child hosts reaped")


def test_close_waits_for_fd_handoff_and_child_survives(artifact, monkeypatch):
    saved = mariamem.load_snapshot(artifact, host_binary=HOST)
    before = fd_count() - len(saved._files)
    entered, proceed = threading.Event(), threading.Event()
    original = subprocess.Popen
    def paused(argv, **kwargs):
        if "--prepared-fd" in argv:
            entered.set()
            assert proceed.wait(10)
        return original(argv, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", paused)
    with ThreadPoolExecutor(max_workers=3) as workers:
        child_future = workers.submit(saved.fork)
        assert entered.wait(10)
        closed = workers.submit(saved.close)
        closed_twice = workers.submit(saved.close)
        time.sleep(0.05)
        assert not closed.done() and not closed_twice.done()
        proceed.set()
        with child_future.result(30) as db:
            closed.result(10)
            closed_twice.result(10)
            initial(db)
    assert fd_count() == before


def test_spawn_and_startup_failure_cleanup(artifact, monkeypatch):
    with mariamem.load_snapshot(artifact, host_binary=HOST) as saved:
        before_fd, before_threads = fd_count(), threading.active_count()
        original = subprocess.Popen
        def rejected(*args, **kwargs):
            raise OSError(errno.EMFILE, "injected process launch failure")
        for _ in range(12):
            with monkeypatch.context() as patch:
                patch.setattr(subprocess, "Popen", rejected)
                with pytest.raises(mariamem.HostError, match="launch failed"):
                    saved.fork()
            with pytest.raises(mariamem.HostError):
                saved.fork(host_binary="/usr/bin/false")
        assert fd_count() == before_fd
        assert threading.active_count() == before_threads
        with saved.fork() as db:
            initial(db)


@pytest.mark.parametrize("phase", ["copy", "adopt"])
def test_partial_import_fd_failure(artifact, monkeypatch, phase):
    import mariamem.snapshot as owned
    before = fd_count()
    original = os.open
    calls = 0
    def open_or_fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError(errno.EMFILE, "injected partial import FD failure")
        return original(*args, **kwargs)
    if phase == "copy":
        monkeypatch.setattr(owned.os, "open", open_or_fail)
    else:
        original_adopt = owned.Snapshot._adopt
        def fail_adopt(self, *args, **kwargs):
            with monkeypatch.context() as patch:
                patch.setattr(owned.os, "open", open_or_fail)
                return original_adopt(self, *args, **kwargs)
        monkeypatch.setattr(owned.Snapshot, "_adopt", fail_adopt)
    with pytest.raises(OSError, match="partial import"):
        mariamem.load_snapshot(artifact, host_binary=HOST)
    assert fd_count() == before


def test_created_temporary_template():
    before = fd_count()
    with mariamem.start(host_binary=HOST) as source:
        sql(source, "CREATE TABLE owned_items(id INT PRIMARY KEY,label VARCHAR(32),payload LONGBLOB) ENGINE=InnoDB")
        sql(source, "INSERT INTO owned_items VALUES(1,'seed',REPEAT('a',1024)),(2,'seed',REPEAT('b',1024)),(3,'seed',REPEAT('c',1024))")
        source.wait_disconnected()
        with source.snapshot() as saved:
            assert not hasattr(saved, "path")
            with saved.fork() as child:
                initial(child)
    assert fd_count() == before


def test_modified_child_creates_new_baseline_without_changing_parent(artifact):
    before = fd_count()
    with mariamem.load_snapshot(artifact, host_binary=HOST) as parent:
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
