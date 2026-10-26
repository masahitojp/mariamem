"""Public Live ownership and late-handle collection through a framed subprocess."""
import time

import pytest
import mariamem
from mariamem._session import Session
from test_owned_snapshot_unit import fake_host


@pytest.fixture
def live_host(fake_host):
    source=fake_host.read_text().replace("'protocol':2,", "'protocol':2,'capabilities':['live-v1'],")
    source=source.replace('release_slow=threading.Event()', 'release_slow=threading.Event();generations={};parents={};fail_close=False')
    source=source.replace(' global seq\n', ' global seq,fail_close\n')
    source=source.replace("'late_snapshot'):release_slow", "'late_snapshot','late_live'):release_slow")
    source=source.replace(" elif op in ('db_close','snapshot_close'):", ''' elif op in ('live_create','late_live'):
  with lock:seq+=1;h=seq;handles[h]='live';generations[h]=0;parents[h]=r.get('handle')
  out.update(live={'handle':h,'host':'127.0.0.1','port':4000+h,'user':'root','password':'','database':'test'},status={'state':'ready','generation':0,'active_connections':0})
 elif op=='fail_live_close':fail_close=True
 elif op=='live_close' and fail_close:
  out.update(ok=False,error={'code':'unusable','stage':'live_close','message':'injected cleanup failure'},closed=True)
 elif op=='live_reset':
  h=r['handle']
  if parents[h] not in handles:out.update(ok=False,error={'code':'closed','stage':'live_precondition','message':'snapshot closed'},closed=False)
  else:
   generations[h]+=1
   out['status']={'state':'ready','generation':generations[h],'active_connections':0}
 elif op=='live_status':out['status']={'state':'ready','generation':generations[r['handle']],'active_connections':0}
 elif op in ('db_close','snapshot_close','live_close'):''')
    fake_host.write_text(source)
    return fake_host


def prepared(host):
    return mariamem.start(host_binary=host).snapshot()


def wait_handles(session, expected):
    deadline=time.monotonic()+3
    while session.request('stats')['handles']!=expected:
        assert time.monotonic()<deadline,'late handle leaked'
        time.sleep(.005)


def test_public_live_metadata_reset_and_exact_owner_release(live_host):
    with prepared(live_host) as saved:
        session=saved._session
        assert session._refs==1
        with saved.live() as live:
            assert isinstance(live,mariamem.Live)
            assert session._refs==2
            original=live.connection_info()
            live.reset(timeout=2,drain_timeout=.1)
            assert live.status()['generation']==1
            assert live.connection_info()==original
            assert session.request('stats')['handles']==2
        assert live.closed and live.connection_info()==original
        assert live.status()['state']=='closed'
        live.close()
        assert session._refs==1
        assert session.request('stats')['handles']==1
    assert session._process.poll() is not None and not session.root.exists()


def test_old_host_refuses_only_new_live_entry(fake_host):
    with prepared(fake_host) as saved:
        with pytest.raises(mariamem.HostError) as caught:saved.live()
        assert caught.value.code=='unsupported' and caught.value.stage=='live_capability'
        assert saved._session._refs==1
        with saved.fork() as child:assert not child.closed


@pytest.mark.parametrize('value',[True,False,0,-1,float('nan'),float('inf'),'5'])
def test_invalid_reset_does_not_send_or_mutate(live_host,value):
    with prepared(live_host) as saved, saved.live() as live:
        for options in [dict(timeout=value),dict(drain_timeout=value)]:
            with pytest.raises(ValueError):live.reset(**options)
        assert live.status()['generation']==0


def test_closed_baseline_does_not_close_live_or_deadlock(live_host):
    saved=prepared(live_host);live=saved.live();session=saved._session
    try:
        saved.close()
        assert session._refs==1 and not live.closed
        with pytest.raises(mariamem.HostError) as caught:live.reset()
        assert caught.value.code=='closed' and not caught.value.closed
        assert live.status()['generation']==0
    finally:live.close()
    assert session._process.poll() is not None


def test_late_live_creation_is_closed_without_terminating_baseline(live_host):
    with prepared(live_host) as saved:
        session=saved._session
        with pytest.raises(TimeoutError):session.request('late_live',handle=saved._handle,response_timeout=.01)
        session.request('release_slow')
        wait_handles(session,1)
        assert session._refs==1 and not session.failed


def test_interrupt_during_live_creation_collects_late_handle(live_host,monkeypatch):
    import mariamem._session as module
    with prepared(live_host) as saved:
        original=module._Reply
        class InterruptReply(original):
            def __init__(self):
                super().__init__()
                self.ready.wait=lambda timeout=None:(_ for _ in ()).throw(KeyboardInterrupt())
        with monkeypatch.context() as patch:
            patch.setattr(module,'_Reply',InterruptReply)
            with pytest.raises(KeyboardInterrupt):saved._session.request('late_live',handle=saved._handle)
        saved._session.request('release_slow')
        wait_handles(saved._session,1)
        assert saved._session._refs==1


def test_application_error_preserved_with_cleanup_error(live_host):
    with prepared(live_host) as saved:
        live=saved.live();saved._session.request('fail_live_close')
        with pytest.raises(ExceptionGroup) as caught:
            with live:raise AssertionError('application failure')
        assert isinstance(caught.value.exceptions[0],AssertionError)
        assert isinstance(caught.value.exceptions[1],mariamem.HostError)
        assert saved._session._refs==1 and live.closed
        with pytest.raises(mariamem.HostError):live.close()
        assert saved._session._refs==1
