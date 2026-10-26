"""Real TCP ownership/gating tests for the experiment relay; no SQL emulation."""
import importlib.util
from pathlib import Path
import socket
import socketserver
import threading
import time

import pytest

spec=importlib.util.spec_from_file_location('e2e_live_relay',Path(__file__).parent/'e2e_guest_spike/live.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Backend:
    def __init__(self,identity):
        self.id=identity;self.closed=False
        class Echo(socketserver.BaseRequestHandler):
            def handle(handler):
                handler.request.sendall(identity.encode())
                while True:
                    data=handler.request.recv(65536)
                    if not data:return
                    handler.request.sendall(data)
        class Server(socketserver.ThreadingTCPServer):daemon_threads=True
        self.server=Server(('127.0.0.1',0),Echo)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
    def connection_info(self):return dict(host='127.0.0.1',port=self.server.server_address[1])
    def wait_disconnected(self,timeout):pass
    def close(self):
        if not self.closed:self.server.shutdown();self.server.server_close();self.thread.join(timeout=1);self.closed=True


def opened(relay):
    c=socket.create_connection(('127.0.0.1',relay.port),timeout=2)
    assert c.recv(1) in [b'A',b'B']
    return c


def test_stream_data_busy_and_generation_replace_without_changing_port():
    a,b=Backend('A'),Backend('B');items=iter([a,b]);events=[]
    relay=module.LiveRelay(lambda:next(items),lambda event,**fields:events.append(dict(event=event,**fields)))
    try:
        port=relay.port;c=opened(relay)
        payload=b'byte;stream\x00'*10000;c.sendall(payload)
        received=bytearray()
        while len(received)<len(payload):received.extend(c.recv(65536))
        assert bytes(received)==payload
        with pytest.raises(module.LiveBusy):relay.reset(timeout=.03)
        assert relay.state=='ready' and relay.generation==0 and not a.closed
        c.close();relay.reset(timeout=2)
        assert relay.port==port and relay.generation==1 and a.closed
        with socket.create_connection(('127.0.0.1',port),timeout=1) as c:assert c.recv(1)==b'B'
        deadline=time.monotonic()+2
        while relay.active:assert time.monotonic()<deadline;time.sleep(.005)
    finally:relay.close()
    assert b.closed and events[-1]['threads_stopped'] and events[-1]['forced_clients']==0


def test_drain_refuses_new_clients_and_failed_replace_needs_explicit_retry():
    a,b=Backend('A'),Backend('B');relay=module.LiveRelay(lambda:a);held=opened(relay);caught=[]
    try:
        def reset():
            try:relay.reset(timeout=.3)
            except module.LiveBusy as e:caught.append(e)
        t=threading.Thread(target=reset);t.start()
        deadline=time.monotonic()+1
        while relay.state!='draining':assert time.monotonic()<deadline;time.sleep(.002)
        with socket.create_connection(('127.0.0.1',relay.port),timeout=1) as c:assert c.recv(1)==b''
        t.join(timeout=1);assert len(caught)==1 and not t.is_alive()
        held.close()
        def fail():raise ValueError('injected replacement failure')
        relay.factory=fail
        with pytest.raises(module.LiveFailed) as e:relay.reset(timeout=2)
        assert isinstance(e.value.__cause__,ValueError) and relay.state=='failed' and not a.closed
        with socket.create_connection(('127.0.0.1',relay.port),timeout=1) as c:assert c.recv(1)==b''
        relay.factory=lambda:b;relay.reset(timeout=2)
        assert relay.state=='ready' and a.closed and relay.generation==1
    finally:held.close();relay.close()
