"""Experimental L2 endpoint: fresh connections only; active sessions block reset.

Test-only relay over existing Snapshot/Fork. It does not preserve SQL sessions,
parse/replay MySQL, change the guest, or expose a product API.
"""
import select
import socket
import threading
import time


class LiveBusy(RuntimeError):
    code='busy'
    stage='drain'


class LiveFailed(RuntimeError):
    code='reset_failed'
    stage='replace'


class LiveRelay:
    def __init__(self,factory,record=lambda *args,**kwargs:None):
        self.factory,self.record=factory,record
        self._cv=threading.Condition()
        self._reset_lock=threading.Lock()
        self._clients=set();self._threads=[]
        self.backend=factory()
        self.generation=0;self.state='ready'
        self._listener=socket.socket()
        self._listener.bind(('127.0.0.1',0));self._listener.listen();self._listener.settimeout(.1)
        self.port=self._listener.getsockname()[1]
        self._acceptor=threading.Thread(target=self._accept,daemon=True);self._acceptor.start()
        self.record('relay_started',port=self.port,generation=self.generation)

    @property
    def active(self):
        with self._cv:return len(self._clients)

    def _accept(self):
        while True:
            try:client,_=self._listener.accept()
            except socket.timeout:continue
            except OSError:return
            with self._cv:
                if self.state!='ready':client.close();continue
                info=self.backend.connection_info()
                self._clients.add(client)
                thread=threading.Thread(target=self._forward,args=(client,info),daemon=True)
                self._threads.append(thread);thread.start()

    def _forward(self,client,info):
        upstream=None
        try:
            upstream=socket.create_connection((info['host'],info['port']),timeout=5)
            client.settimeout(2);upstream.settimeout(2)
            while True:
                readable,_,_=select.select([client,upstream],[],[],.1)
                for source in readable:
                    data=source.recv(65536)
                    if not data:return
                    (upstream if source is client else client).sendall(data)
                with self._cv:
                    if self.state=='closed':return
        except OSError:
            return
        finally:
            for connection in [client,upstream]:
                if connection is not None:
                    try:connection.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                    connection.close()
            with self._cv:self._clients.discard(client);self._cv.notify_all()

    def reset(self,timeout=5):
        if timeout<=0:raise ValueError('drain timeout must be positive')
        # Startup/close use the SDK's own bounded settings; timeout here bounds drain.
        with self._reset_lock:
            with self._cv:
                if self.state=='closed':raise LiveFailed('relay closed')
                previous=self.state;self.state='draining';self._cv.notify_all()
                deadline=time.monotonic()+timeout
                while self._clients:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:
                        self.state=previous
                        self.record('relay_busy',generation=self.generation,active=len(self._clients))
                        raise LiveBusy('active physical SQL sessions must close before reset')
                    self._cv.wait(remaining)
                self.state='switching'
            old=self.backend;candidate=None
            try:
                candidate=self.factory()
                old.wait_disconnected(timeout=5)
                old.close()
                with self._cv:
                    self.backend=candidate;self.generation+=1;self.state='ready'
                self.record('guest_reset',generation=self.generation,port=self.port,old_closed=old.closed,
                            child_id=candidate.id,backend_port=candidate.connection_info()['port'])
            except BaseException as error:
                with self._cv:self.state='failed'
                try:
                    if candidate is not None:candidate.close()
                finally:self.record('relay_failed',generation=self.generation,error_type=type(error).__name__)
                raise LiveFailed('replacement failed; no next test may be admitted') from error

    def close(self):
        with self._reset_lock:
            with self._cv:
                if self.state=='closed':return
                self.state='closed';clients=list(self._clients)
            self._listener.close()
            for client in clients:
                try:client.shutdown(socket.SHUT_RDWR)
                except OSError:pass
            self._acceptor.join(timeout=2)
            for thread in self._threads:thread.join(timeout=2)
            self.backend.close()
            stopped=not self._acceptor.is_alive() and not any(t.is_alive() for t in self._threads)
            self.record('relay_closed',active=self.active,forced_clients=len(clients),threads_stopped=stopped,
                        child_closed=self.backend.closed)
            if not stopped or self.active:raise RuntimeError('relay workers did not stop')
