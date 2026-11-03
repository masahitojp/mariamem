"""Bounded SDK admission using a real control transport and controlled host."""
from concurrent.futures import ThreadPoolExecutor
import shutil
import time
from pathlib import Path
import sys

import pytest
import mariamem
from test_owned_snapshot_unit import fake_host  # noqa: F401
from mariamem._session import Session


def test_cap_timeout_retains_child_and_next_close_releases_slot(fake_host):
    with mariamem.start(host_binary=fake_host) as root:
        with root.snapshot(max_forks=1) as baseline:
            assert baseline.max_forks == 1
            with pytest.raises(AttributeError):
                baseline.max_forks = 2
            child = baseline.fork()
            try:
                with pytest.raises(mariamem.HostError) as error:
                    baseline.fork(timeout=.04)
                assert (error.value.code, error.value.stage) == ("pool_timeout", "fork_wait")
                assert child.status()["state"] == "ready"
                assert baseline._session.request("stats")["reservations"] == 0
            finally:
                child.close()
            with baseline.fork(timeout=1) as replacement:
                assert replacement.status()["state"] == "ready"


@pytest.mark.parametrize("different_host", [False, True])
def test_parent_close_wakes_capacity_wait_without_closing_child(fake_host, tmp_path, different_host):
    other = tmp_path / "other-host"
    shutil.copy2(fake_host, other)
    root = mariamem.start(host_binary=fake_host)
    baseline = root.snapshot(max_forks=1)
    child = baseline.fork()
    session = baseline._session
    before = session.request("stats")["reserve_calls"]
    try:
        with ThreadPoolExecutor(1) as pool:
            waiting = pool.submit(baseline.fork, host_binary=other if different_host else fake_host)
            deadline = time.monotonic() + 2
            while session.request("stats")["reserve_calls"] <= before:
                assert time.monotonic() < deadline
                time.sleep(.005)
            baseline.close()
            with pytest.raises(mariamem.HostError) as error:
                waiting.result(2)
            assert error.value.code == "closed"
            assert child.status()["state"] == "ready"
            assert session.request("stats")["handles"] == 1
            with session._lock:
                assert session._refs == 1
            assert not session._handoffs  # A full source never starts a target.
    finally:
        baseline.close()
        child.close()
        root.close()
    assert session._process.poll() == 0


@pytest.mark.parametrize("value", [True, 0, -1, 2**100, float("nan")])
def test_invalid_capacity_and_wait_preserve_existing_owners(fake_host, value):
    with mariamem.start(host_binary=fake_host) as root:
        with pytest.raises((ValueError, TypeError)):
            root.snapshot(max_forks=value)
        assert root.status()["state"] == "ready"
        with root.snapshot(max_forks=1) as baseline:
            with baseline.fork() as child:
                before = baseline._session.request("stats")["reserve_calls"]
                with pytest.raises((ValueError, TypeError)):
                    baseline.fork(timeout=value)
                assert baseline._session.request("stats")["reserve_calls"] == before
                assert child.status()["state"] == "ready"


def test_missing_capability_rejected_before_consumption(fake_host):
    with mariamem.start(host_binary=fake_host) as root:
        root._session.capabilities = ()
        with pytest.raises(mariamem.HostError) as error:
            root.snapshot()
        assert error.value.stage == "fork_capability"
        assert not root.closed
        assert root.status()["state"] == "ready"


@pytest.mark.parametrize('mismatch', ['capability', 'guest'])
def test_unsupported_target_releases_only_unused_source_reservation(fake_host, tmp_path, mismatch):
    old = tmp_path/'unsupported-host'
    script = fake_host.read_text()
    if mismatch == 'capability':
        script = script.replace("['fork-limit-v1']", '[]')
    else:
        script = script.replace("'guest_sha256':'guest'", "'guest_sha256':'wrong'")
    old.write_text(script)
    old.chmod(0o755)
    with mariamem.start(host_binary=fake_host) as root:
        with root.snapshot(max_forks=1) as baseline:
            with pytest.raises(mariamem.HostError, match='fork-limit-v1|guest identity mismatch'):
                baseline.fork(host_binary=old, timeout=1)
            assert baseline._session.request('stats')['reservations'] == 0
            assert baseline._session._refs == 1 and not baseline._session._handoffs
            with baseline.fork(timeout=1) as child:
                assert child.status()['state'] == 'ready'


def test_parent_releases_session_when_remote_notification_fails(fake_host):
    root = mariamem.start(host_binary=fake_host)
    baseline = root.snapshot(max_forks=1)
    session = baseline._session

    class Owner:
        def parent(self):
            return baseline

        def parent_closed(self):
            raise OSError("injected notification failure")

    owner = Owner()
    session._handoffs.add(owner)
    try:
        with pytest.raises(OSError, match="notification failure"):
            baseline.close()
        assert session._process.poll() == 0
        assert baseline._close_done.is_set()
    finally:
        session._handoffs.discard(owner)


def test_remote_child_holds_source_capacity_until_disposal(fake_host, tmp_path):
    other = tmp_path / "target-host"
    shutil.copy2(fake_host, other)
    with mariamem.start(host_binary=fake_host) as root:
        with root.snapshot(max_forks=1) as baseline:
            remote = baseline.fork(host_binary=other)
            owner = remote._remote
            try:
                assert not owner.scratch.exists()
                assert remote.diagnostics["host_pid"] != baseline._session._process.pid
                with pytest.raises(mariamem.HostError, match="capacity"):
                    baseline.fork(timeout=.03)
                assert remote.status()["state"] == "ready"
            finally:
                remote.close()
            assert owner.done and not baseline._session._handoffs
            with baseline.fork(timeout=1):
                pass


def test_remote_capture_settles_origin_and_parent_close_preserves_target(fake_host, tmp_path):
    other = tmp_path / "target-host"
    shutil.copy2(fake_host, other)
    with mariamem.start(host_binary=fake_host) as root:
        with root.snapshot(max_forks=1) as baseline:
            child = baseline.fork(host_binary=other)
            owner = child._remote
            with child.snapshot(max_forks=1) as next_baseline:
                assert owner.done
                with baseline.fork(timeout=1):
                    pass
                baseline.close()
                with next_baseline.fork(timeout=1) as grandchild:
                    assert grandchild.status()["state"] == "ready"


def test_remote_local_preparation_failure_reclaims_export(fake_host, tmp_path, monkeypatch):
    other = tmp_path / "target-host"
    shutil.copy2(fake_host, other)
    with mariamem.start(host_binary=fake_host) as root:
        with root.snapshot(max_forks=1) as baseline:
            original = Path.mkdir
            bad_parent = tmp_path / "fail-local-preparation"

            def fail(path, *args, **kwargs):
                if path == bad_parent:
                    raise OSError("injected log parent failure")
                return original(path, *args, **kwargs)

            monkeypatch.setattr(Path, "mkdir", fail)
            with pytest.raises(OSError, match="log parent failure"):
                baseline.fork(host_binary=other, log_path=bad_parent / "db.log")
            assert not baseline._session._handoffs
            assert not list(baseline._session.root.glob("handoff-*"))
            with baseline.fork(timeout=1):
                pass


def test_stuck_control_writer_has_bounded_callers_and_one_writer(tmp_path):
    stop = tmp_path / "exit"
    host = tmp_path / "stuck-host"
    host.write_text("#!" + sys.executable + "\n" + f'''
import json,sys,time
from pathlib import Path
print(json.dumps(dict(event='ready',protocol=2,capabilities=[],guest_sha256='guest')),flush=True)
r=json.loads(sys.stdin.readline())
print(json.dumps(dict(id=r['id'],ok=True)),flush=True)
while not Path({str(stop)!r}).exists(): time.sleep(.01)
''')
    host.chmod(0o755)
    session = Session(host)
    session.retain()
    try:
        session.request("park", response_timeout=1)
        writer = session._writer
        started = time.monotonic()
        for _ in range(4):
            with pytest.raises(TimeoutError):
                session.request("blocked", response_timeout=.04, data="x"*(256*1024))
            assert session._writer is writer and writer.is_alive()
            with session._lock:
                assert len(session._writes) <= 1
            assert session._process.poll() is None
        assert time.monotonic()-started < 2
    finally:
        stop.touch()
        assert session._exited.wait(3)
        session.release()
        assert session._reaped.wait(3)
