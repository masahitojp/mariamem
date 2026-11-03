"""Real framed subprocesses hold replies after allocation; no real guest fault."""
from pathlib import Path
import threading
import time

import pytest
import mariamem
import mariamem._session as transport
from test_owned_snapshot_unit import fake_host  # noqa: F401


def gated_host(template, path, operation):
    marker = path.with_suffix('.entered')
    script = template.read_text()
    script = script.replace('def send(v):\n with lock:', f'''
fault_local=threading.local();fault_release=threading.Event();fault_armed=False
def send(v):
 if fault_armed and getattr(fault_local,'op',None)=={operation!r} and not v.get('full'):
  open({str(marker)!r},'w').close()
  if not fault_release.wait(10): raise RuntimeError('test failed to release reply barrier')
 with lock:''')
    script = script.replace(' global seq\n', ' global seq,fault_armed\n')
    script = script.replace(" op=r['op'];out={'id':r.get('id'),'ok':True}", ''' op=r['op'];out={'id':r.get('id'),'ok':True}
 fault_local.op=op
 if op=='fault_arm':fault_armed=True;send(out);return
 if op=='fault_release':fault_release.set();send(out);return''')
    path.write_text(script)
    path.chmod(0o755)
    return path, marker


def eventually(check):
    deadline = time.monotonic()+3
    while not check():
        assert time.monotonic() < deadline, 'late ownership did not settle'
        time.sleep(.005)


@pytest.mark.parametrize('operation', ['fork_reserve', 'handoff', 'start'])
@pytest.mark.parametrize('interrupt', [False, True])
def test_late_capacity_export_or_start_reclaims_once_and_preserves_other_owner(
        fake_host, tmp_path, monkeypatch, operation, interrupt):
    source_path, source_marker = gated_host(fake_host, tmp_path/'source-host', operation)
    target_path, target_marker = gated_host(fake_host, tmp_path/'target-host', operation)
    with mariamem.start(host_binary=source_path) as root:
        with root.snapshot(max_forks=1) as baseline:
            source = baseline._session
            target = transport.Session(target_path)
            target.retain()  # An independent target owner must survive timeout.
            sibling = target.request('start')['database']['handle']
            gate_session = target if operation == 'start' else source
            marker = target_marker if operation == 'start' else source_marker
            gate_session.request('fault_arm')
            factories = []
            original_request = transport.Session.request
            reply_type = transport._Reply
            caller = threading.current_thread()

            class InterruptReply(reply_type):
                def __init__(self):
                    super().__init__()
                    if threading.current_thread() is caller:
                        def stop(timeout=None):
                            eventually(marker.exists)
                            raise KeyboardInterrupt('injected capacity/transfer interruption')
                        self.ready.wait = stop

            def request(session, op, **fields):
                if interrupt and session is gate_session and op == operation:
                    with monkeypatch.context() as patch:
                        patch.setattr(transport, '_Reply', InterruptReply)
                        return original_request(session, op, **fields)
                return original_request(session, op, **fields)

            def session_factory(binary):
                assert Path(binary) == target_path
                factories.append(binary)
                return target

            try:
                with monkeypatch.context() as patch:
                    patch.setattr(transport.Session, 'request', request)
                    patch.setattr(transport, 'Session', session_factory)
                    patch.setattr(mariamem, '_STARTUP_REPLY_MARGIN', .08)
                    with pytest.raises(KeyboardInterrupt if interrupt else TimeoutError):
                        baseline.fork(host_binary=target_path, timeout=.1, startup_timeout=.02)
                assert marker.exists()
                assert bool(factories) == (operation != 'fork_reserve')
                assert not source.failed and not target.failed
                assert target.request('status', handle=sibling)['state'] == 'ready'
                assert source.request('stats')['reservations'] == 1
                with pytest.raises(mariamem.HostError) as error:
                    baseline.fork(timeout=.02)
                assert error.value.code == 'pool_timeout'
                gate_session.request('fault_release')

                def settled():
                    a, b = source.request('stats'), target.request('stats')
                    with source._lock, target._lock:
                        return (not source._handoffs and not source._pending and not target._pending
                                and source._refs == target._refs == 1
                                and a['reservations'] == 0 and b['handles'] == 1)
                eventually(settled)
                calls = target.request('stats')['close_calls']
                assert len(calls) == int(operation == 'start'), calls
                assert target.request('status', handle=sibling)['state'] == 'ready'
                with baseline.fork(timeout=1):
                    pass
            finally:
                gate_session.request('fault_release')
                target.request('db_close', handle=sibling)
                target.release()
