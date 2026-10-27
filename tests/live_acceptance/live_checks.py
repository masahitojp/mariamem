"""Real public Live busy/parent lifetime, plus common Go core fault injection."""
import socket
import threading
import time

import pytest
from conftest import connect,rows,record


@pytest.mark.parametrize('transaction',[False,True],ids=['idle','transaction'])
def test_held_physical_session_refuses_reset_then_recovers(isolated_live,transaction):
    import mariamem,MySQLdb
    live,_=isolated_live;info=live.connection_info();held=connect(info);generation=live.status()['generation'];failures=[]
    try:
        with held.cursor() as c:
            if transaction:c.execute('START TRANSACTION')
            c.execute("INSERT INTO orders_order(sku,quantity,status) VALUES('BUSY',1,'ready')")
        def reset():
            try:live.reset(timeout=5,drain_timeout=.5)
            except mariamem.Busy as error:failures.append(error)
        thread=threading.Thread(target=reset);thread.start()
        deadline=time.monotonic()+3
        while live.status()['state']!='draining':
            assert time.monotonic()<deadline;time.sleep(.005)
        with pytest.raises(MySQLdb.Error):connect(info)
        thread.join(timeout=3);assert not thread.is_alive() and len(failures)==1
        assert failures[0].code=='busy' and failures[0].stage=='live_drain' and not failures[0].closed
        assert live.status()['state']=='ready' and live.status()['generation']==generation
        with held.cursor() as c:
            c.execute("SELECT sku FROM orders_order WHERE sku='BUSY'");assert c.fetchall()==(('BUSY',),)
        if transaction:held.rollback()
    finally:held.close()
    live.reset(timeout=5)
    assert live.status()['generation']==generation+1 and rows(info)==[['SEED',2,'ready']]
    record('busy_control_pass',transaction=transaction,busy_code=failures[0].code,new_handshake_refused=True,old_data_preserved=True)


def test_closed_parent_preserves_current_live_and_blocks_reset(isolated_live):
    import mariamem
    live,saved=isolated_live;info=live.connection_info();generation=live.status()['generation']
    saved.close()
    assert rows(info)==[['SEED',2,'ready']]
    with pytest.raises(mariamem.HostError) as failure:live.reset()
    assert failure.value.code=='closed' and not failure.value.closed
    assert live.status()['state']=='ready' and live.status()['generation']==generation
    record('parent_lifetime_control_pass',old_child_preserved=True,reset_refused=True)


def test_real_go_replacement_failure_blocks_admission_and_retry(replacement_probe):
    import MySQLdb
    from go_provider import GoControlError
    live,owner=replacement_probe;generation=live.status()['generation'];info=live.connection_info()
    owner.request('probe_fail',id=live.handle)
    with pytest.raises(GoControlError) as failure:live.reset()
    assert 'E2E_INJECTED_FORK_FAILURE' in str(failure.value)
    assert failure.value.code=='unusable' and failure.value.stage=='live_replace'
    assert live.status()['state']=='failed' and live.status()['generation']==generation
    with pytest.raises(MySQLdb.Error):connect(info)
    owner.request('probe_recover',id=live.handle);live.reset()
    assert live.status()['state']=='ready' and live.status()['generation']==generation+1
    assert rows(info)==[['SEED',2,'ready']]
    host,port=live.original_address.rsplit(':',1)
    with pytest.raises(OSError):socket.create_connection((host,int(port)),timeout=.5)
    record('failed_replace_control_pass',route='common_go_core_fault_probe',no_admission=True,explicit_retry=True,original_cause_retained=True,old_endpoint_closed=True)
