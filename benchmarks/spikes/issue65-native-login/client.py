#!/usr/bin/env python3
"""Test-client packet fixture only. No server-side encoder lives here."""
import argparse
from decimal import Decimal
import json
import hashlib
import shutil
import os
from pathlib import Path
import select
import struct
import subprocess
import time
import traceback

CAPS=1|4|8|512|8192|32768|65536|131072|524288|262144

def length(data,pos=0):
    n=data[pos];pos+=1
    if n<251:return n,pos
    if n==251:return None,pos
    size={252:2,253:3,254:8}[n]
    return int.from_bytes(data[pos:pos+size],'little'),pos+size

def strings(data,count):
    pos=0;values=[]
    for _ in range(count):
        n,pos=length(data,pos)
        if n is None:values.append(None)
        else:values.append(data[pos:pos+n]);pos+=n
    assert pos==len(data),(data,pos)
    return values

class Client:
    def __init__(self,process):self.p=process;self.packets=[];self.seq=0
    def exact(self,n):
        result=b'';deadline=time.monotonic()+10
        while len(result)<n:
            ready,_,_=select.select([self.p.stdout],[],[],max(0,deadline-time.monotonic()))
            assert ready,'server output timeout'
            chunk=os.read(self.p.stdout.fileno(),n-len(result))
            assert chunk,'unexpected server EOF'
            result+=chunk
        return result
    def receive(self):
        h=self.exact(4);n=int.from_bytes(h[:3],'little');assert n<=1<<20,n
        assert h[3]==self.seq,('sequence',h[3],self.seq)
        self.seq=(self.seq+1)&255;body=self.exact(n)
        self.packets.append({'direction':'server','sequence':h[3],'hex':body.hex()});return body
    def send(self,body,seq=0):
        frame=len(body).to_bytes(3,'little')+bytes([seq])+body
        self.p.stdin.write(frame);self.p.stdin.flush();self.seq=(seq+1)&255
        self.packets.append({'direction':'client','sequence':seq,'hex':body.hex()})
    def auth(self,user=b'test',secure=True):
        self.seq=0;g=self.receive();assert g[0]==10,('expected greeting',g)
        end=g.index(0,1);version=g[1:end].decode();pos=end+1
        connection=int.from_bytes(g[pos:pos+4],'little');pos+=4+8+1
        caps=int.from_bytes(g[pos:pos+2],'little')|(int.from_bytes(g[pos+5:pos+7],'little')<<16)
        assert caps==CAPS,('capabilities',caps,CAPS)
        assert g.endswith(b'mysql_native_password\0')
        flags=CAPS if secure else CAPS&~32768
        response=struct.pack('<IIB23s',flags,1<<20,45,b'')+user+b'\0'
        response+=(b'\x14'+b'x'*20) if secure else b'placeholder\0'
        response+=b'test\0mysql_native_password\0'
        self.send(response,1);reply=self.receive();assert reply[0]==0,('authentication',reply)
        return {'connection_id':connection,'version':version,'capabilities':caps,'secure_encoding':secure}
    def columns(self,n):
        cols=[]
        for _ in range(n):
            body=self.receive();names=[];pos=0
            for _ in range(6):
                size,pos=length(body,pos);names.append(body[pos:pos+size]);pos+=size
            fixed,pos=length(body,pos);assert fixed==12
            cols.append({'name':names[4].decode(),'type':body[pos+6],'flags':int.from_bytes(body[pos+7:pos+9],'little')})
        if n:
            eof=self.receive();assert eof[0]==254 and len(eof)<9,eof
        return cols
    def result(self,binary=False):
        head=self.receive();assert head[0]!=255,('unexpected SQL error',head)
        n,pos=length(head);assert pos==len(head)
        cols=self.columns(n);rows=[]
        while True:
            row=self.receive()
            if row[0]==254 and len(row)<9:break
            if not binary:rows.append(strings(row,n));continue
            assert row[0]==0;nullbytes=(n+9)//8;nulls=int.from_bytes(row[1:1+nullbytes],'little');pos=1+nullbytes;values=[]
            for i,col in enumerate(cols):
                if nulls&(1<<(i+2)):values.append(None);continue
                kind=col['type']
                if kind in [1,2,3,8,9]:
                    size={1:1,2:2,3:4,8:8,9:4}[kind]
                    values.append(int.from_bytes(row[pos:pos+size],'little',signed=not(col['flags']&32)));pos+=size
                elif kind in [4,5]:
                    size=4 if kind==4 else 8;values.append(struct.unpack('<f' if kind==4 else '<d',row[pos:pos+size])[0]);pos+=size
                else:
                    size,pos=length(row,pos);value=row[pos:pos+size];values.append(Decimal(value.decode()) if kind==246 else value);pos+=size
            assert pos==len(row),(row,pos,cols);rows.append(values)
        return cols,rows
    def query(self,sql):self.send(b'\x03'+sql.encode());return self.result()
    def prepare(self,sql):
        self.send(b'\x16'+sql.encode());head=self.receive();assert head[0]==0,head
        stmt,ncols,nparams=struct.unpack('<IHH',head[1:9]);params=self.columns(nparams);cols=self.columns(ncols)
        return stmt,params,cols
    def execute(self,stmt,n,s,types=True):
        p=struct.pack('<IBI',stmt,0,1)+b'\x04'+bytes([types])
        if types:p+=struct.pack('<HHH',8,253,6)
        p+=struct.pack('<q',n)+bytes([len(s)])+s
        self.send(b'\x17'+p);return self.result(True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);args=parser.parse_args();args.evidence.mkdir(exist_ok=True)
    source_root=Path(__file__).resolve().parents[3]
    patch=source_root/'guest/experimental.patch'
    (args.evidence/'identity.json').write_text(json.dumps({'experimental_patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),'client_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'probe_sha256':hashlib.sha256(Path(__file__).with_name('probe.cc').read_bytes()).hexdigest()},indent=2)+'\n')
    shutil.copy2(args.evidence.parent/'source-files.json',args.evidence/'source-files.json')
    command=['docker','exec','-i','mariamem-issue65-login','sh','-c','ulimit -c 0; mkdir -p /exp/temp/data; cd /exp/temp/data; exec timeout -k 2 45 /exp/temp/probe']
    checks=[];failure=None;sessions=[]
    with (args.evidence/'server.txt').open('wb') as stderr:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,bufsize=0)
        client=Client(process)
        try:
            first=client.auth();sessions.append(first);checks.append('native_handshake_placeholder_secure')
            cols,rows=client.query("SELECT 7 AS n, NULL AS z, 'a' AS s")
            assert [x['name'] for x in cols]==['n','z','s'];assert rows==[[b'7',None,b'a']];checks.append('native_text_metadata_null')
            _,rows=client.query('SELECT CURRENT_USER(), USER(), DATABASE()');assert rows==[[b'root@localhost',b'root@localhost',b'test']],rows;checks.append('canonical_identity_initial_db')
            client.send(b'\x03SELECT * FROM test.no_such_table');err=client.receive();assert err[0]==255 and int.from_bytes(err[1:3],'little')==1146 and err[4:9]==b'42S02';checks.append('native_sql_error')
            _,rows=client.query('SELECT 8');assert rows==[[b'8']];checks.append('following_query_after_sql_error')
            stmt,params,cols=client.prepare('SELECT ? + 1 AS n, ? AS s, ? AS z');assert len(params)==len(cols)==3;checks.append('native_prepare_metadata')
            _,rows=client.execute(stmt,41,b'a\0b');assert rows==[[42,b'a\0b',None]],rows;checks.append('native_execute_binary_null_NUL')
            _,rows=client.execute(stmt,99,b'',False);assert rows==[[100,b'',None]],rows;checks.append('native_execute_type_reuse')
            bad=struct.pack('<IBI',stmt,0,1)+b'\x04\x01'+struct.pack('<HHH',8,253,6)+b'abc'
            client.send(b'\x17'+bad);err=client.receive();assert err[0]==255 and int.from_bytes(err[1:3],'little')==1210;checks.append('native_malformed_int64_error')
            client.send(b'\x19'+struct.pack('<I',stmt));client.send(b'\x0e');assert client.receive()[0]==0;checks.append('close_has_no_reply_then_ping')
            client.send(b'\x17'+bad);err=client.receive();assert err[0]==255 and int.from_bytes(err[1:3],'little')==1243;checks.append('closed_statement_rejected')
            client.send(b'\x03SET @leak=1');assert client.receive()[0]==0
            client.send(b'\x01');second=client.auth(b'',False);sessions.append(second);assert first['connection_id']!=second['connection_id'];checks.append('quit_retire_then_second_native_login_legacy')
            _,rows=client.query('SELECT @leak');assert rows==[[None]];checks.append('second_session_state_is_fresh')
            client.send(b'\x01');process.stdin.close();rc=process.wait(timeout=15);assert rc==0,('server exit',rc)
            server=(args.evidence/'server.txt').read_text()
            assert server.count('PASS:embedded_MYSQL_BIND')==2,server
            assert 'PASS:product_fresh_bootstrap' in server and server.count('SESSION_RETIRED result=0')==2 and 'PASS:all_sessions_retired native_decodes=3' in server,server
            checks+=['product_fresh_routine_bootstrap','embedded_MYSQL_BIND_before_after','two_sessions_retired_and_queues_joined']
            for name in checks:print('PASS:'+name)
            print('PASS:step3A_complete')
        except BaseException as exc:
            failure=repr(exc)+' at '+','.join(f'{Path(x.filename).name}:{x.lineno}' for x in traceback.extract_tb(exc.__traceback__));print('FAIL:'+failure)
            try:process.stdin.close()
            except (OSError,ValueError):pass
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=3)
        finally:
            (args.evidence/'packets.json').write_text(json.dumps(client.packets,indent=2)+'\n')
            (args.evidence/'result.json').write_text(json.dumps({'scope':'step3A native login/output only','passed':failure is None,'checks':checks,'failure':failure,'process_exit_code':process.returncode,'sessions':sessions,'command':command},indent=2)+'\n')
        if failure:raise SystemExit(1)

if __name__=='__main__':main()
