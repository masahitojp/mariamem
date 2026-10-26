"""Real guest SQL/transaction, reset-failure and old-generation admission controls."""
import contextlib
import socket
import threading
import time

import pytest
from conftest import connect,rows,record
from live import LiveBusy,LiveFailed


def test_busy_transaction_refuses_new_handshake_then_recovers(isolated_live):
    relay,_=isolated_live
    info=relay.backend.connection_info();info['port']=relay.port
    held=connect(info);generation=relay.generation;old_port=relay.backend.connection_info()['port']
    failures=[]
    try:
        with held.cursor() as cursor:
            cursor.execute('START TRANSACTION')
            cursor.execute("INSERT INTO orders_order(sku,quantity,status) VALUES('BUSY',1,'ready')")
        def reset():
            try:relay.reset(timeout=.8)
            except LiveBusy as error:failures.append(error)
        t=threading.Thread(target=reset);t.start()
        deadline=time.monotonic()+2
        while relay.state!='draining':
            assert time.monotonic()<deadline;time.sleep(.005)
        import MySQLdb
        with pytest.raises(MySQLdb.Error):connect(info)
        t.join(timeout=2);assert not t.is_alive() and len(failures)==1
        assert relay.state=='ready' and relay.generation==generation
        held.rollback()
    finally:held.close()
    relay.reset(timeout=5)
    assert relay.generation==generation+1 and rows(relay.backend.connection_info())==[['SEED',2,'ready']]
    with pytest.raises(OSError):socket.create_connection(('127.0.0.1',old_port),timeout=.5)
    record('busy_control_pass',busy_code=failures[0].code,old_endpoint_closed=True,new_handshake_refused=True)


def test_replacement_failure_blocks_admission_and_explicit_retry(isolated_live):
    relay,saved=isolated_live
    original=relay.backend;generation=relay.generation
    def fail():raise RuntimeError('E2E_INJECTED_FORK_FAILURE')
    relay.factory=fail
    with pytest.raises(LiveFailed) as failure:relay.reset()
    assert str(failure.value.__cause__)=='E2E_INJECTED_FORK_FAILURE'
    assert relay.state=='failed' and relay.backend is original and not original.closed
    import MySQLdb
    info=original.connection_info();info['port']=relay.port
    with pytest.raises(MySQLdb.Error):connect(info)
    assert relay.generation==generation
    relay.factory=saved.fork
    relay.reset()
    assert relay.state=='ready' and original.closed and relay.generation==generation+1
    assert rows(relay.backend.connection_info())==[['SEED',2,'ready']]
    record('failed_replace_control_pass',no_admission=True,explicit_retry=True,original_cause_retained=True)
