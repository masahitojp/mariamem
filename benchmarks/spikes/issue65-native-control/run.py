#!/usr/bin/env python3
"""Real native endpoint/control experiment. MySQL parsing is test-client only."""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading
import time
import traceback

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('client3a',HERE.parent/'issue65-native-login/client.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
INPUT=1048581;OUTPUT=65536;HEADER=struct.Struct('<BIIQQQ')
OPEN,DATA,ACK,EOF,QUIESCE,STOP,STATS,HOLD,INSPECT,EXPIRE=range(1,11)
READY,OPENED,REPLY,RAW,RETIRED,POISON,CREDIT,STATE,STATS_REPLY,QUIESCED,REJECTED,DONE=range(100,112)

def compact(body):return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'prefix_hex':body[:128].hex()}

class Peer:
    def __init__(self,slot,generation):
        self.slot=slot;self.generation=generation;self.buffer=bytearray();self.received=0;self.input_sent=0;self.consumed=0;self.ack=True;self.retired=None;self.phase='handshake';self.command=0;self.admit_wait=False

class Root:
    def __init__(self,evidence,name):
        self.evidence=evidence;self.name=name;self.cv=threading.Condition();self.write_lock=threading.Lock();self.responses={};self.peers={};self.request=0;self.epoch=None;self.poison=None;self.done=None;self.failure=None;self.events=[];self.wires=[];self.start=time.monotonic();self.ready=None
        self.stderr=(evidence/'server.txt').open('wb')
        self.process=subprocess.Popen(['docker','exec','-i','mariamem-issue65-control','sh','-c','ulimit -c 0; rm -rf /exp/temp/data; mkdir -p /exp/temp/data; cd /exp/temp/data; exec timeout -k 2 30 /exp/temp/control'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,bufsize=0)
        self.reader=threading.Thread(target=self.read_loop,daemon=True);self.reader.start();self.wait(lambda:self.epoch is not None)
    def wait(self,predicate,timeout=4):
        end=time.monotonic()+timeout
        with self.cv:
            while not predicate():
                assert self.failure is None,self.failure
                left=end-time.monotonic();assert left>0,('timeout',self.name,self.events[-8:])
                self.cv.wait(left)
    def exact_frame(self,n):
        b=b''
        while len(b)<n:
            x=os.read(self.process.stdout.fileno(),n-len(b))
            if not x:raise EOFError('control process EOF')
            b+=x
        return b
    def read_loop(self):
        try:
            while True:
                n=int.from_bytes(self.exact_frame(4),'little');assert 33<=n<=65569,n
                data=self.exact_frame(n);kind,req,slot,epoch,gen,value=HEADER.unpack(data[:33]);body=data[33:]
                with self.cv:
                    if kind==READY:self.epoch=epoch;self.ready=json.loads(body)
                    key=(slot,gen)
                    if kind==OPENED:self.peers[key]=Peer(slot,gen)
                    p=self.peers.get(key)
                    if kind==RAW:
                        assert p is not None,(kind,slot,gen)
                        assert value==p.received,(value,p.received)
                        p.buffer+=body;p.received+=len(body)
                    elif kind==CREDIT:
                        if p:p.consumed=value
                    elif kind==STATE:
                        if p:p.phase=body.decode();p.command=value
                    elif kind==RETIRED:
                        if p:p.retired={'result':value,**json.loads(body)}
                    elif kind==POISON:self.poison=body.decode()
                    elif kind==DONE:self.done=json.loads(body)
                    elif kind==REPLY and not req and body==b'admit_wait':
                        if p:p.admit_wait=True
                    if req:self.responses[req]=(kind,slot,gen,value,body)
                    if kind!=RAW and kind!=CREDIT:self.events.append({'t':round(time.monotonic()-self.start,6),'kind':kind,'request':req,'slot':slot,'generation':gen,'value':value,'text':body.decode()})
                    ack=(p,p.received) if kind==RAW and p.ack else None
                    self.cv.notify_all()
                if ack:self.send(ACK,peer=ack[0],value=ack[1])
        except BaseException as exc:
            with self.cv:
                if self.done is None:self.failure=repr(exc)
                self.cv.notify_all()
    def send(self,kind,request=0,peer=None,value=0,body=b'',epoch=None):
        packet=HEADER.pack(kind,request,peer.slot if peer else 0,epoch if epoch is not None else self.epoch,peer.generation if peer else 0,value)+body
        with self.write_lock:
            self.process.stdin.write(struct.pack('<I',len(packet))+packet);self.process.stdin.flush()
    def rpc(self,kind,peer=None,value=0,body=b'',epoch=None):
        with self.cv:self.request+=1;request=self.request
        self.send(kind,request,peer,value,body,epoch)
        self.wait(lambda:request in self.responses)
        with self.cv:return self.responses.pop(request)
    def open(self,ms=5000):
        response=self.rpc(OPEN,value=ms);assert response[0]==OPENED,response
        return Wire(self,self.peers[(response[1],response[2])])
    def raw(self,p,data,respect=True):
        pos=0
        while pos<len(data):
            n=min(65536,len(data)-pos)
            if respect:
                self.wait(lambda:INPUT-(p.input_sent-p.consumed)>0)
                with self.cv:n=min(n,INPUT-(p.input_sent-p.consumed))
            offset=p.input_sent;p.input_sent+=n
            self.send(DATA,peer=p,value=offset,body=data[pos:pos+n]);pos+=n
    def ack(self,p,enabled):
        with self.cv:p.ack=enabled;offset=p.received
        if enabled:self.send(ACK,peer=p,value=offset)
    def stats(self):
        r=self.rpc(STATS);assert r[0]==STATS_REPLY,r;return json.loads(r[4])
    def until(self,predicate,timeout=4):
        end=time.monotonic()+timeout
        while True:
            stats=self.stats()
            if predicate(stats):return stats
            assert time.monotonic()<end,('state timeout',stats)
            time.sleep(.005)
    def state_of(self,wire,stats):return next((x for x in stats['sessions'] if (x['slot'],x['generation'])==(wire.peer.slot,wire.peer.generation)),None)
    def phase(self,wire,phase):return self.until(lambda st:(self.state_of(wire,st) or {}).get('phase')==phase)
    def quiesce(self,rollback=False):return self.rpc(QUIESCE,value=int(rollback))
    def retired(self,wire):self.wait(lambda:wire.peer.retired is not None);return wire.peer.retired
    def poison_joined(self,cause):
        self.wait(lambda:self.poison is not None);assert self.poison==cause,self.poison
        return self.until(lambda st:not st['sessions'] and st['started']==st['joined'])
    def stop(self):
        if self.done is None and self.process.poll() is None:
            self.send(STOP);self.wait(lambda:self.done is not None,timeout=8)
        try:self.process.stdin.close()
        except (OSError,ValueError):pass
        rc=self.process.wait(timeout=8);self.reader.join(timeout=2);self.stderr.close()
        assert rc==0,('server exit',rc)
        assert self.done['started']==self.done['joined'],self.done
        (self.evidence/'events.json').write_text(json.dumps(self.events,indent=2)+'\n')
        (self.evidence/'final.json').write_text(json.dumps(self.done,indent=2)+'\n')
    def fail_cleanup(self):
        try:self.stop()
        except BaseException:
            try:self.process.stdin.close()
            except (OSError,ValueError):pass
            subprocess.run(['docker','exec','mariamem-issue65-control','pkill','-TERM','-x','control'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            self.stderr.close()
            (self.evidence/'events.json').write_text(json.dumps(self.events,indent=2)+'\n')

class Wire(old.Client):
    def __init__(self,root,peer):self.root=root;self.peer=peer;self.packets=[];self.seq=0;root.wires.append(self)
    def exact(self,n):
        self.root.wait(lambda:len(self.peer.buffer)>=n or self.peer.retired is not None)
        with self.root.cv:
            assert len(self.peer.buffer)>=n,('native EOF',self.peer.retired,n,len(self.peer.buffer))
            result=bytes(self.peer.buffer[:n]);del self.peer.buffer[:n];return result
    def receive(self):
        value=super().receive()
        if len(value)>256:self.packets[-1]={'direction':'server',**compact(value)}
        return value
    def send(self,body,seq=0):
        self.root.raw(self.peer,len(body).to_bytes(3,'little')+bytes([seq])+body);self.seq=(seq+1)&255
        self.packets.append({'direction':'client','sequence':seq,**compact(body)})
    def login(self):self.auth();self.root.phase(self,'idle');return self
    def idle(self):return self.root.phase(self,'idle')
    def ok(self,sql):self.send(b'\x03'+sql.encode());body=self.receive();assert body[0]==0,body;self.idle()
    def quit(self):self.send(b'\x01');return self.root.retired(self)

results=[];ROOT=None

def case(name,fn,args):
    global ROOT
    folder=args.evidence/name;folder.mkdir();root=None;record={'name':name,'passed':False};start=time.monotonic()
    try:
        root=Root(folder,name);ROOT=root
        details=fn(root);root.stop();record.update(passed=True,details=details,elapsed_seconds=round(time.monotonic()-start,6));print('PASS:'+name,flush=True)
    except BaseException as exc:
        record.update(process_exit_code=root.process.poll() if root else None,error=repr(exc),traceback=[f'{Path(x.filename).name}:{x.lineno}' for x in traceback.extract_tb(exc.__traceback__)])
        if root:root.fail_cleanup()
        print('FAIL:'+name+':'+repr(exc),flush=True)
    finally:
        if root:
            record['process_exit_code']=root.process.poll()
            (folder/'packets.json').write_text(json.dumps([{'slot':w.peer.slot,'generation':w.peer.generation,'packets':w.packets} for w in root.wires],indent=2)+'\n')
        (folder/'result.json').write_text(json.dumps(record,indent=2)+'\n');results.append(record)
    if not record['passed']:raise RuntimeError(name)

def concurrent_case(root):
    a=root.open().login();b=root.open().login()
    a.send(b'\x03SELECT SLEEP(0.7)');root.phase(a,'executing')
    assert b.query('SELECT 22')[1]==[[b'22']]
    assert (root.state_of(a,root.stats()) or {})['phase']=='executing'
    assert a.result()[1]==[[b'0']];a.idle();b.idle()
    # One client withholds delivery acknowledgement. It cannot monopolize control.
    root.ack(a.peer,False);a.send(b"\x03SELECT REPEAT('x',200000)")
    stalled=root.until(lambda st:(root.state_of(a,st) or {}).get('outstanding')==OUTPUT)
    before=time.monotonic();assert b.query('SELECT 23')[1]==[[b'23']];busy=root.quiesce();assert busy[0]==REJECTED and busy[3]==1,busy
    assert (root.state_of(a,root.stats()) or {})['outstanding']==OUTPUT
    progress_seconds=time.monotonic()-before
    root.ack(a.peer,True);rows=a.result()[1];assert rows==[[b'x'*200000]];a.idle();b.idle()
    # Even drained native queue is busy until the physical-write offset is acked.
    root.ack(a.peer,False);a.send(b'\x03SELECT 24');root.phase(a,'flushing');busy=root.quiesce();assert busy[0]==REJECTED and busy[3]==1
    root.ack(a.peer,True);assert a.result()[1]==[[b'24']];a.idle()
    a.send(b'\x03SELECT 31');a.send(b'\x03SELECT 32');assert a.result()[1]==[[b'31']];a.seq=1;assert a.result()[1]==[[b'32']];a.idle()
    # Prepared statements and their types belong to the concurrent THDs.
    def prepared(w):
        stmt,_,_=w.prepare('SELECT ? + 1 AS n, ? AS s, ? AS z');assert w.execute(stmt,41,b'a\0b')[1]==[[42,b'a\0b',None]];w.send(b'\x19'+struct.pack('<I',stmt));w.send(b'\x0e');assert w.receive()[0]==0;w.idle()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(prepared,[a,b]))
    old_token=root.state_of(a,root.stats())['command'];a.send(b'\x03SELECT SLEEP(0.2)');root.phase(a,'executing');late=root.rpc(EXPIRE,a.peer,old_token);assert late[0]==REJECTED and late[4]==b'stale_timer';assert a.result()[1]==[[b'0']];a.idle()
    assert not root.stats()['poisoned'];a.quit();b.quit()
    return {'checks':['real_concurrent_SQL','slow_output_other_session_control_progress','output_ack_lease','pipeline_serial_native_responses','concurrent_prepared_THDs','no_response_close','late_timer_ignored'],'blocked_snapshot':stalled,'progress_observed_seconds':round(progress_seconds,6)}

def gates(root):
    a=root.open().login();b=root.open().login();a.send(b'\x03SELECT SLEEP(0.2)');root.phase(a,'executing');assert root.quiesce()[3]==1;assert b.query('SELECT 1')[1]==[[b'1']];assert a.result()[1]==[[b'0']];a.idle();b.idle()
    a.ok('START TRANSACTION');state=root.state_of(a,root.stats());assert state['status']&1,state
    rejection=root.quiesce();assert rejection[0]==REJECTED and rejection[3]==2,rejection;a.ok('ROLLBACK')
    root.raw(a.peer,b'\x01');root.phase(a,'receiving');assert root.quiesce()[3]==1;root.raw(a.peer,b'\0\0\0\x0e');a.seq=1;assert a.receive()[0]==0;a.idle()
    assert root.rpc(HOLD,a.peer,1)[0]==REPLY;a.send(b'\x03INSERT INTO test.effects VALUES (1)');root.wait(lambda:a.peer.admit_wait)
    fence=root.quiesce();assert fence[0]==QUIESCED,fence
    assert root.rpc(HOLD,a.peer,0)[0]==REPLY;root.retired(a)
    oracle=root.rpc(INSPECT);assert oracle[3]==0,oracle
    b.send(b'\x0e');root.retired(b);assert root.stats()['denied']>=1
    return {'checks':['busy_rejection_preserves_DB','transaction_rejection_preserves_DB','partial_header_busy','queued_insert_cannot_cross_fence','no_new_commands_after_fence'],'effects_count':oracle[3]}

def rollback_fence(root):
    a=root.open().login();a.ok('START TRANSACTION');assert root.quiesce(True)[0]==QUIESCED
    return {'checks':['rollback_override_fence_only'],'storage_capture':'not tested'}

def timeout_case(root,mode):
    a=root.open(600).login();b=root.open().login()
    if mode=='query':a.send(b'\x03SELECT SLEEP(10)');root.phase(a,'executing')
    elif mode=='input':root.raw(a.peer,b'\x01');root.phase(a,'receiving')
    else:
        root.ack(a.peer,False);a.send(b"\x03SELECT REPEAT('x',200000)");root.until(lambda st:(root.state_of(a,st) or {}).get('outstanding')==OUTPUT);assert b.query('SELECT 1')[1]==[[b'1']]
    start=time.monotonic();final=root.poison_joined('deadline');assert root.rpc(OPEN,value=5000)[0]==REJECTED
    return {'checks':[mode+'_deadline_poison_join','all_waiters_retire_before_free'],'join_observed_seconds':round(time.monotonic()-start,6),'stats':final}

def handshake_timeout(root):
    stalled=root.open(500);healthy=root.open().login();root.retired(stalled)
    assert not root.stats()['poisoned'];assert healthy.query('SELECT 1')[1]==[[b'1']];healthy.quit()
    return {'checks':['handshake_deadline_session_only']}

def pending_case(root,eof):
    a=root.open().login();b=root.open().login();a.send(b'\x03SELECT SLEEP(10)');root.phase(a,'executing');root.raw(a.peer,b'\0'*INPUT)
    snapshot=root.until(lambda st:(root.state_of(a,st) or {}).get('input')==INPUT)
    if eof:root.send(EOF,peer=a.peer)
    else:root.raw(a.peer,b'x',respect=False)
    final=root.poison_joined('unexpected_peer_eof' if eof else 'pending_input_overflow');assert final['retired_input_peak']==INPUT,final
    return {'checks':['EOF_observed_behind_full_input' if eof else 'one_byte_overflow_aborts_instance','input_payload_budget_exact','both_native_workers_joined'],'full_input':snapshot,'final':final}

def capacity(root):
    clients=[root.open(10000).login() for _ in range(16)];before=root.stats();full=root.rpc(OPEN,value=5000);assert full[0]==REJECTED and full[3]==3,full;assert root.stats()['started']==16
    old_peer=clients[0].peer;clients[0].ok('SET @leak=9');clients[0].quit();new=root.open().login();assert new.peer.slot==old_peer.slot and new.peer.generation>old_peer.generation
    assert new.query('SELECT @leak')[1]==[[None]]
    for kind in [ACK,EOF,DATA]:
        reply=root.rpc(kind,old_peer,0,b'\x00' if kind==DATA else b'');assert reply[0]==REJECTED and reply[3]==5,reply
    wrong=root.rpc(EOF,new.peer,epoch=root.epoch+1);assert wrong[0]==REJECTED and wrong[3]==5
    assert new.query('SELECT 42')[1]==[[b'42']];new.quit()
    for w in clients[1:]:w.quit()
    after=root.until(lambda st:st['joined']==17)
    return {'checks':['sixteen_live_native_sessions','seventeenth_rejected_without_worker','reuse_only_after_join','old_generation_DATA_ACK_EOF_ignored','wrong_instance_epoch_ignored','session_state_isolated'],'before':before,'after':after}

def framing(root):
    a=root.open().login();b=root.open().login()
    suffix=b'*/SELECT 1';sql=b'/*'+b'x'*(1048576-2-len(suffix))+suffix;assert len(sql)==1048576
    a.send(b'\x03'+sql);assert a.result()[1]==[[b'1']];a.idle()
    root.raw(a.peer,(1048578).to_bytes(3,'little')+b'\x00');warm=root.retired(a);assert warm['net_error']==1153,warm
    assert b.query('SELECT 42')[1]==[[b'42']];b.idle()
    c=root.open().login();c.send(b'\x0e',seq=2);wrong=root.retired(c);assert wrong['executions']==0,wrong
    d=root.open();d.seq=0;assert d.receive()[0]==10;d.send(b'\xff\x01\x00',seq=0);previous=root.retired(d);assert previous['net_error']==1156,previous
    assert b.query('SELECT 43')[1]==[[b'43']];b.quit()
    return {'checks':['maximum_SQL_frame_accepted','warm_buffer_over_limit_header_rejected_before_payload','wrong_sequence_not_dispatched','previous_sequence_ERR_rejected_by_server_NET'],'warm':warm,'wrong':wrong,'previous_ERR':previous}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);parser.add_argument('--only');args=parser.parse_args();args.evidence.mkdir(exist_ok=True,parents=True)
    repo=HERE.parents[2];workspace=repo.parent
    pins=json.loads((workspace/'evidence/source-files.json').read_text())
    for name,pin in pins.items():
        assert hashlib.sha256((workspace/'temp/source'/name).read_bytes()).hexdigest()==pin['after_sha256'],name
    files=[repo/'guest/experimental.patch',workspace/'temp/control',workspace/'temp/native/libmysqld/libmariadbd.a',workspace/'evidence/source-files.json',repo/'guest/routine_bootstrap.inc',HERE.parent/'issue65-native-login/client.py',*sorted(HERE.glob('*.py')),*sorted(HERE.glob('*.cc')),*sorted(HERE.glob('*.h')),*sorted(HERE.glob('*.inc')),HERE/'compile.sh']
    hashes={str(p.relative_to(workspace)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    identity={'base':json.loads(subprocess.check_output([sys.executable,str(repo/'scripts/git_identity.py'),'--root',str(repo),'inspect','HEAD'])),'hashes':hashes}
    (args.evidence/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    cases={'concurrency':concurrent_case,'gates':gates,'rollback_fence':rollback_fence,'query_deadline':lambda r:timeout_case(r,'query'),'input_deadline':lambda r:timeout_case(r,'input'),'output_deadline':lambda r:timeout_case(r,'output'),'handshake_deadline':handshake_timeout,'full_input_EOF':lambda r:pending_case(r,True),'input_overflow':lambda r:pending_case(r,False),'capacity_generation':capacity,'native_framing':framing}
    failed=False
    try:
        for name,fn in cases.items():
            if args.only and name!=args.only:continue
            case(name,fn,args)
    except BaseException:failed=True
    finally:
        identity['unchanged_after_run']=all(hashlib.sha256((workspace/name).read_bytes()).hexdigest()==sha for name,sha in hashes.items())
        (args.evidence/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
        (args.evidence/'result.json').write_text(json.dumps({'scope':'3B native control only','passed':not failed and identity['unchanged_after_run'],'cases':results},indent=2)+'\n')
        failed=failed or not identity['unchanged_after_run']
    raise SystemExit(int(failed))

if __name__=='__main__':main()
