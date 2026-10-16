"""Deterministic ownership/routing tests using a real framed-control subprocess.

File import validation remains at internal/snapshot; public persistence is gone.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time

import pytest
import mariamem
from mariamem._session import Session


@pytest.fixture
def fake_host(tmp_path):
    path = tmp_path / "host"
    path.write_text("#!" + sys.executable + "\n" + r'''
import json,os,sys,threading,time
lock=threading.Lock();handles={};seq=0;release_slow=threading.Event()

def send(v):
 with lock:
  print(json.dumps(v),flush=True)

def call(r):
 global seq
 op=r['op'];out={'id':r.get('id'),'ok':True}
 if op=='cancel':return
 if op=='invalid':send({'id':999999,'ok':True});return
 if op=='malformed':send([]);return
 if op=='bad_error':send({'id':r['id'],'ok':False,'error':'broken'});return
 if op in ('start','fork') and r.get('log_path','').endswith('reject-startup'):
  out.update(ok=False,error={'code':'guest_start','stage':'guest_launch','message':'injected guest startup failure'})
  send(out);return
 if op in ('slow','late_database','late_snapshot'):release_slow.wait(5)
 if op=='release_slow':release_slow.set()
 if op in ('start','fork','late_database'):
  with lock:seq+=1;h=seq;handles[h]='db'
  if r.get('log_path'):open(r['log_path'],'x').write('db log\n')
  out['database']={'handle':h,'id':str(h).zfill(32),'host':'127.0.0.1','port':3000+h,'user':'root','password':'','database':'test','pid':os.getpid(),'runtime_pid':os.getpid(),'capabilities':['snapshot','fork'],'max_connections':16}
 elif op in ('snapshot','late_snapshot'):
  with lock:seq+=1;h=seq;handles[h]='snapshot';handles.pop(r.get('handle'),None)
  out.update(snapshot=h,closed=True)
 elif op in ('db_close','snapshot_close'):
  with lock:handles.pop(r['handle'],None)
  out['closed']=True
 elif op=='status':out.update(state='ready',active_connections=0,busy=False)
 elif op=='logs':out['logs']='log tail'
 elif op=='stats':out['handles']=len(handles)
 elif op=='shutdown':send(out);os._exit(0)
 send(out)
print(json.dumps({'event':'ready','protocol':2,'guest_sha256':'guest','pid':os.getpid()}),flush=True)
threads=[]
for line in sys.stdin:
 r=json.loads(line);t=threading.Thread(target=call,args=(r,));threads.append(t);t.start()
for t in threads:t.join()
''')
    path.chmod(0o755)
    return path


def test_public_persistence_removed(fake_host):
    assert not hasattr(mariamem, "load_snapshot")
    assert not hasattr(mariamem.Database, "snapshot_to")
    assert not hasattr(mariamem.Snapshot, "open")
    with pytest.raises(TypeError, match="handle"):
        mariamem.start(host_binary=fake_host, snapshot="saved")
    with pytest.raises(TypeError, match="Database.snapshot"):
        mariamem.Snapshot("saved")


def test_ownership_consumption_and_last_owner_reaps(fake_host):
    root = mariamem.start(host_binary=fake_host)
    session = root._session
    baseline = root.snapshot()
    assert root.closed and session._process.poll() is None
    first, second = baseline.fork(), baseline.fork()
    assert first.diagnostics["host_pid"] == second.diagnostics["host_pid"]
    assert first.connection_info()["port"] != second.connection_info()["port"]
    baseline.close()
    first.close()
    assert second.status()["state"] == "ready"
    assert session._process.poll() is None
    second.close()
    assert session._process.poll() == 0
    assert not session.root.exists()
    assert not session._reader.is_alive()
    baseline.close()
    with pytest.raises(ValueError, match="closed"):
        baseline.fork()


def test_independent_roots_own_independent_hosts(fake_host):
    with mariamem.start(host_binary=fake_host) as a, mariamem.start(host_binary=fake_host) as b:
        assert a.diagnostics["host_pid"] != b.diagnostics["host_pid"]
        a.close()
        assert b.status()["state"] == "ready"


def test_out_of_order_responses_do_not_serialize_other_requests(fake_host):
    session = Session(fake_host)
    session.retain()
    try:
        with ThreadPoolExecutor(2) as pool:
            slow = pool.submit(session.request, "slow")
            fast = pool.submit(session.request, "stats")
            assert fast.result(2)["handles"] == 0
            assert not slow.done()
            session.request("release_slow")
            assert slow.result(2)["ok"]
    finally:
        session.release()


@pytest.mark.parametrize("operation", ["late_database", "late_snapshot"])
def test_timeout_collects_late_created_handles_without_killing_other_owner(fake_host, operation):
    session = Session(fake_host)
    session.retain()
    try:
        with pytest.raises(TimeoutError):
            session.request(operation, response_timeout=.01)
        assert session.request("stats")["handles"] == 0
        session.request("release_slow")
        until = time.monotonic() + 3
        while True:
            with session._lock:
                drained = not session._pending and session._refs == 1
            if drained:
                break
            assert time.monotonic() < until
            time.sleep(.01)
        assert session.request("stats")["handles"] == 0
        assert session._process.poll() is None
    finally:
        session.release()


@pytest.mark.parametrize("operation", ["invalid", "malformed", "bad_error"])
def test_protocol_failure_wakes_all_waiters_and_stays_within_lineage(fake_host, operation):
    with mariamem.start(host_binary=fake_host) as other:
        session = Session(fake_host)
        session.retain()
        try:
            with ThreadPoolExecutor(2) as pool:
                slow = pool.submit(session.request, "slow")
                invalid = pool.submit(session.request, operation)
                for future in (slow, invalid):
                    with pytest.raises(mariamem.HostError) as error:
                        future.result(2)
                    assert error.value.closed and error.value.code == "unusable"
            assert other.status()["state"] == "ready"
        finally:
            session.release()


@pytest.mark.parametrize("key", ["query_timeout", "startup_timeout", "shutdown_timeout"])
@pytest.mark.parametrize("value", [0, -1, float('inf'), float('nan'), '1'])
def test_invalid_options_rejected_without_host_launch(key, value):
    with pytest.raises(ValueError, match="positive"):
        mariamem.start(**{key:value})


def test_child_close_discards_default_log_but_keeps_tail(fake_host):
    with mariamem.start(host_binary=fake_host) as root:
        with root.snapshot() as baseline:
            child = baseline.fork()
            path = child.log_path
            assert path.exists()
            child.close()
            assert not path.exists()
            assert "db log" in child.logs
            assert baseline._session._process.poll() is None


def test_unreturned_child_is_closed_when_ready_adoption_fails(fake_host, monkeypatch):
    with mariamem.start(host_binary=fake_host) as root:
        with root.snapshot() as baseline:
            session = baseline._session
            original = session.request
            def incomplete(operation, *args, **kwargs):
                reply = original(operation, *args, **kwargs)
                if operation == "fork":
                    del reply["database"]["capabilities"]
                return reply
            monkeypatch.setattr(session, "request", incomplete)
            with pytest.raises(KeyError, match="capabilities"):
                baseline.fork()
            assert session.request("stats")["handles"] == 1
            assert session._process.poll() is None


def test_snapshot_accepts_no_path_argument():
    # Argument binding rejects these before any DB or host access.
    db = mariamem.Database.__new__(mariamem.Database)
    with pytest.raises(TypeError):
        db.snapshot("saved")
    with pytest.raises(TypeError):
        db.snapshot(path="saved")
    with pytest.raises(TypeError):
        db.snapshot(destination="saved")


def test_reader_start_failure_reaps_launched_host(fake_host, monkeypatch):
    import subprocess
    import threading
    created = []
    original = subprocess.Popen
    def launch(*args, **kwargs):
        process = original(*args, **kwargs)
        created.append((process, Path(kwargs["env"]["TMPDIR"])))
        return process
    def reject(thread):
        raise RuntimeError("injected reader startup failure")
    monkeypatch.setattr(subprocess, "Popen", launch)
    monkeypatch.setattr(threading.Thread, "start", reject)
    with pytest.raises(RuntimeError, match="reader startup"):
        Session(fake_host)
    process, scratch = created[0]
    assert process.poll() is not None
    assert process.stdin.closed and process.stdout.closed
    assert not scratch.exists()


def test_invalid_log_path_rejected_before_host_creation(monkeypatch):
    import subprocess
    def unexpected(*args, **kwargs):
        pytest.fail("invalid log path launched a host")
    monkeypatch.setattr(subprocess, "Popen", unexpected)
    with pytest.raises(TypeError):
        mariamem.start(log_path=object())


def test_host_log_open_failure_removes_owned_scratch(fake_host, monkeypatch):
    import tempfile
    created = []
    original_temp = tempfile.TemporaryDirectory
    original_open = Path.open
    def temporary(*args, **kwargs):
        value = original_temp(*args, **kwargs)
        created.append(Path(value.name))
        return value
    def reject(path, *args, **kwargs):
        if path.name == "host.log":
            raise OSError("injected log-open failure")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", temporary)
    monkeypatch.setattr(Path, "open", reject)
    with pytest.raises(mariamem.HostError, match="log-open failure"):
        Session(fake_host)
    assert len(created) == 1 and not created[0].exists()


def test_child_start_failure_keeps_closed_flag_and_preserves_baseline(fake_host, tmp_path):
    with mariamem.start(host_binary=fake_host) as root:
        with root.snapshot() as baseline:
            with pytest.raises(mariamem.HostError) as failed:
                baseline.fork(log_path=tmp_path / "reject-startup")
            assert failed.value.closed
            assert failed.value.code == "guest_start"
            assert failed.value.stage == "guest_launch"
            assert baseline._session.request("stats")["handles"] == 1
            with baseline.fork() as child:
                assert child.status()["state"] == "ready"
