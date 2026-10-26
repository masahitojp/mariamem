"""Test-only JSON control channel to a Go public-API Snapshot/Fork owner."""
import json
import os
from pathlib import Path
import select
import subprocess


class GoOwner:
    def __init__(self,record):
        self.record=record
        self.temp=Path(os.environ['E2E_OUTPUT'])/'go-owner-tmp';self.temp.mkdir()
        self.log=(Path(os.environ['E2E_OUTPUT'])/'go-owner.txt').open('w')
        schema=Path(__file__).parent.parent/'e2e_native_control/goapp/schema.sql'
        self.process=subprocess.Popen([os.environ['E2E_GO_OWNER'],str(schema)],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=self.log,text=True,env=dict(os.environ,TMPDIR=str(self.temp)))
        try:
            ready=self._read();assert ready=={'ready':True,'source_consumed':True},ready
            self.record('baseline_captured',kind='go',source_consumed=True,api='Go public Snapshot/Fork')
        except BaseException:
            self.process.terminate();self.process.wait(timeout=10);self.log.close();raise

    def _read(self):
        readable,_,_=select.select([self.process.stdout],[],[],90)
        if not readable:raise TimeoutError('Go owner response timeout')
        line=self.process.stdout.readline()
        if not line:raise RuntimeError('Go owner exited before reply')
        return json.loads(line)

    def request(self,op,**fields):
        self.process.stdin.write(json.dumps(dict(op=op,**fields))+'\n');self.process.stdin.flush()
        reply=self._read()
        if not reply.get('ok'):raise RuntimeError(reply.get('error','owner failed'))
        return reply

    def fork(self):return GoChild(self,self.request('fork'))

    def close(self):
        try:self.request('shutdown')
        finally:
            self.process.stdin.close()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
            self.log.close()
        empty=not any(self.temp.iterdir())
        self.record('guest_host_cleanup',kind='go',reaped=self.process.returncode==0,directory_removed=empty)
        assert self.process.returncode==0 and empty
        self.temp.rmdir()


class GoChild:
    def __init__(self,owner,reply):self.owner=owner;self.id=reply['id'];self.info=reply['info'];self.closed=False
    def connection_info(self):return dict(self.info)
    def wait_disconnected(self,timeout=5):self.owner.request('wait',id=self.id)
    def close(self):
        if not self.closed:self.closed=self.owner.request('close',id=self.id)['closed']
