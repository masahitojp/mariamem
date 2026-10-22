"""Engine-owned LONG_DATA native/guest differential; no host byte accumulator."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import pymysql
from v06_prepared_call_probe import result_chain
from v06_prepared_p1_probe import close_ping,prepare
from v06_prepared_p2_matrix import payload,query

CASES=('chunks-binary-mixed-parameters','empty-stream-overrides-null',
       'type-reuse-and-change','two-statement-ownership','invalid-index-deferred',
       'wrong-LONG-type','wrong-NULL-type','wrong-TIME-type','reset-stream',
       'close-and-unknown-adjacency','malformed-short-chunks','aggregate-over-1MiB',
       'native-aggregate-overflow','65-parameters-stream-index-64',
       'wrong-DECIMAL-type','wrong-BIT-type','wrong-NEWDECIMAL-type')+tuple(
       f'accepted-type-{typ}' for typ in (15,247,248,249,250,251,254,255))


def connect(info):return pymysql.connect(**info,autocommit=True,charset='utf8mb4',read_timeout=10,write_timeout=10)


def streamed(sid,types,inline=None,reuse=False,nulls=()):
    inline=inline or {}
    mask=bytearray((len(types)+7)//8)
    for i in nulls:mask[i//8]|=1<<(i%8)
    body=struct.pack('<IBI',sid,0,1)+mask+bytes([not reuse])
    if not reuse:body+=b''.join(bytes([t,0]) for t in types)
    return body+b''.join(inline.get(i,b'') for i in range(len(types)))


def chunk(c,sid,index,data):c._execute_command(24,struct.pack('<IH',sid,index)+data)


def row_bytes(data):
    assert len(data)<251
    return (b'\0\0'+bytes([len(data)])+data).hex()


def run(info,name,out):
    out['stage']=name;out['trace']=[];trace=out['trace']
    with connect(info) as c:
        out['version']=query(c,'SELECT VERSION()')[0][0]
        assert out['version'].startswith('12.3.3')
        query(c,'SET NAMES utf8mb4 COLLATE utf8mb4_general_ci')
        def prep(sql):
            sid,metadata=prepare(c,sql);out.setdefault('prepare',[]).append(metadata);return sid
        def execute(body):
            response=result_chain(c,body,allow_error=True);trace.append(response);return response
        if name=='chunks-binary-mixed-parameters':
            sid=prep('SELECT ? AS a,? AS n,? AS b')
            chunk(c,sid,0,b'A\0');chunk(c,sid,2,'日本語'.encode());chunk(c,sid,0,b'B')
            r=execute(streamed(sid,[252,3,252],{1:struct.pack('<i',23)},nulls=(2,)))
            expected=(b'\0\0\x03A\0B'+struct.pack('<i',23)+b'\x09'+'日本語'.encode()).hex()
            assert r[0]['rows']==[expected]
            close_ping(c,sid)
        elif name=='empty-stream-overrides-null':
            sid=prep('SELECT ? AS v');chunk(c,sid,0,b'');chunk(c,sid,0,b'')
            assert execute(streamed(sid,[252],nulls=(0,)))[0]['rows']==[row_bytes(b'')]
            r=execute(payload(sid,[(252,False,None)]));assert r[0]['rows']==['0004']
            close_ping(c,sid)
        elif name=='type-reuse-and-change':
            sid=prep('SELECT ? AS v')
            assert execute(payload(sid,[(252,False,b'first')]))[0]['rows']==[row_bytes(b'first')]
            chunk(c,sid,0,b'long');chunk(c,sid,0,b'-reuse')
            assert execute(streamed(sid,[252],reuse=True))[0]['rows']==[row_bytes(b'long-reuse')]
            assert execute(payload(sid,[(252,False,b'inline')],reuse=True))[0]['rows']==[row_bytes(b'inline')]
            chunk(c,sid,0,'文字'.encode())
            assert execute(streamed(sid,[253]))[0]['rows']==[row_bytes('文字'.encode())]
            close_ping(c,sid)
        elif name=='two-statement-ownership':
            first=prep('SELECT ? AS v');second=prep('SELECT ? AS v')
            chunk(c,first,0,b'first');chunk(c,second,0,b'second')
            assert execute(streamed(second,[252]))[0]['rows']==[row_bytes(b'second')]
            assert execute(streamed(first,[252]))[0]['rows']==[row_bytes(b'first')]
            close_ping(c,second);close_ping(c,first)
        elif name=='invalid-index-deferred':
            sid=prep('SELECT ? AS v');chunk(c,sid,9,b'x')
            c._execute_command(14,b'');assert c._read_packet().is_ok_packet()
            for body in [payload(sid,[(252,False,b'z')]),payload(sid,[(252,False,b'z')]),struct.pack('<IBI',sid,0,1)]:
                r=execute(body);assert r[0]['errno']==1210 and r[0]['sqlstate']=='HY000'
            c._execute_command(26,struct.pack('<I',sid));assert c._read_packet().is_ok_packet()
            assert execute(payload(sid,[(252,False,b'z')]))[0]['rows']==[row_bytes(b'z')]
            close_ping(c,sid)
        elif name.startswith('wrong-'):
            typ={'wrong-LONG-type':3,'wrong-NULL-type':6,'wrong-TIME-type':11,
                 'wrong-DECIMAL-type':0,'wrong-BIT-type':16,'wrong-NEWDECIMAL-type':246}[name]
            sid=prep('SELECT ? AS v');chunk(c,sid,0,b'abc')
            r=execute(streamed(sid,[typ]));assert r[0]['errno']==1210 and r[0]['sqlstate']=='HY000'
            assert execute(payload(sid,[(252,False,b'z')]))[0]['rows']==[row_bytes(b'z')]
            close_ping(c,sid)
        elif name.startswith('accepted-type-'):
            typ=int(name.rsplit('-',1)[1]);sid=prep('SELECT ? AS v');chunk(c,sid,0,b'abc')
            r=execute(streamed(sid,[typ]));assert r[0]['rows']==[row_bytes(b'abc')]
            close_ping(c,sid)
        elif name=='65-parameters-stream-index-64':
            sid=prep('SELECT '+','.join(f'? AS v{i}' for i in range(65)))
            chunk(c,sid,64,b'tail');r=execute(streamed(sid,[252]*65,nulls=range(65)))
            bitmap=bytearray(9)
            for i in range(64):bitmap[(i+2)//8]|=1<<((i+2)%8)
            assert len(r[0]['columns'])==65 and r[0]['rows']==[(b'\0'+bitmap+b'\x04tail').hex()]
            close_ping(c,sid)
        elif name=='reset-stream':
            sid=prep('SELECT ? AS v')
            execute(payload(sid,[(252,False,b'first')]))
            chunk(c,sid,0,b'discarded')
            c._execute_command(26,struct.pack('<I',sid));assert c._read_packet().is_ok_packet()
            assert execute(payload(sid,[(252,False,b'new')],reuse=True))[0]['rows']==[row_bytes(b'new')]
            close_ping(c,sid)
        elif name=='close-and-unknown-adjacency':
            sid=prep('SELECT ? AS v');chunk(c,sid,0,b'discarded');close_ping(c,sid)
            chunk(c,sid,0,b'unknown');c._execute_command(14,b'');assert c._read_packet().is_ok_packet()
            r=execute(payload(sid,[(252,False,b'z')]));assert r[0]['errno']==1243 and r[0]['sqlstate']=='HY000'
            # Keep the opaque ID's original error packet, compare errno/state.
            out['opaque_handle_error']=r[0];trace[-1]=[{'errno':1243,'sqlstate':'HY000'}]
        elif name=='malformed-short-chunks':
            sid=prep('SELECT ? AS v')
            for n in range(6):
                c._execute_command(24,struct.pack('<IH',sid,0)[:n]);c._execute_command(14,b'');assert c._read_packet().is_ok_packet()
            assert execute(payload(sid,[(252,False,b'normal')]))[0]['rows']==[row_bytes(b'normal')]
            close_ping(c,sid)
        elif name=='aggregate-over-1MiB':
            sid=prep('SELECT CAST(OCTET_LENGTH(?) AS SIGNED) AS n,SHA2(?,256) AS sha')
            chunks=[b'A\0B'*233333,b'Z'*700000,b'last']
            data=b''.join(chunks);assert len(data)>1<<20
            out['stream_recipe']={'chunk_sizes':[len(x) for x in chunks],'bytes_per_parameter':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            for data_chunk in chunks:
                chunk(c,sid,0,data_chunk);chunk(c,sid,1,data_chunk)
            r=execute(streamed(sid,[252,252]));row=bytes.fromhex(r[0]['rows'][0])
            assert row==b'\0\0'+struct.pack('<q',len(data))+b'\x40'+hashlib.sha256(data).hexdigest().encode()
            close_ping(c,sid)
        elif name=='native-aggregate-overflow':
            old=int(query(c,'SELECT @@global.max_allowed_packet')[0][0])
            try:
                query(c,'SET GLOBAL max_allowed_packet=4096')
                with connect(info) as limited:
                    sid,meta=prepare(limited,'SELECT ? AS v');out['prepare']=[meta]
                    assert int(query(limited,'SELECT @@session.max_allowed_packet')[0][0])==4096
                    chunk(limited,sid,0,b'a'*3000);chunk(limited,sid,0,b'b'*3000)
                    limited._execute_command(14,b'');assert limited._read_packet().is_ok_packet()
                    r=result_chain(limited,streamed(sid,[252]),allow_error=True);trace.append(r)
                    assert r[0]['errno']==1105 and r[0]['sqlstate']=='HY000'
                    assert query(limited,'SELECT 1')==((1,),)
                    r=result_chain(limited,payload(sid,[(252,False,b'z')]),allow_error=True);trace.append(r)
                    assert r[0]['errno']==1105
                    limited._execute_command(26,struct.pack('<I',sid));assert limited._read_packet().is_ok_packet()
                    r=result_chain(limited,payload(sid,[(252,False,b'z')]),allow_error=True);trace.append(r)
                    assert r[0]['rows']==[row_bytes(b'z')];close_ping(limited,sid)
            finally:query(c,f'SET GLOBAL max_allowed_packet={old}')
        else:raise ValueError(name)
        assert query(c,'SELECT 1')==((1,),)
        out.update(result='PASS',following_query='PASS',no_response_adjacency='PASS');out.pop('stage',None)


def exercise(info=None,host=None):
    result={'scope':'P4 LONG_DATA development matrix; not full P4-P6 acceptance','cases':{},'failures':{}}
    for name in CASES:
        case={};db=None
        try:
            if host:
                import mariamem
                db=mariamem.start(host_binary=host);current=db.connection_info()
            else:current=info
            run(current,name,case)
            if db:db.wait_disconnected(timeout=10);case['active_connections_after']=db.status()['active_connections'];assert case['active_connections_after']==0
        except Exception as error:case.update(result='FAIL',error=repr(error))
        finally:
            if db:
                temp=db.log_path.parent
                try:case['logs']=db.logs;db.close();assert not temp.exists();case['temporary_removed']=True
                except Exception as error:case.update(result='FAIL',cleanup_error=repr(error))
        result['cases'][name]=case
        if case.get('result')!='PASS':result['failures'][name]=case.get('error',case.get('cleanup_error','missing PASS'))
    result['result']='FAIL' if result['failures'] else 'PASS';return result


def comparable(c):return {k:c[k] for k in ('prepare','trace','stream_recipe','following_query','no_response_adjacency') if k in c}


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--host');g.add_argument('--native-port',type=int);p.add_argument('--output',type=Path,required=True);p.add_argument('--reference',type=Path)
    a=p.parse_args();r=exercise(host=a.host,info=dict(host='127.0.0.1',port=a.native_port,user='root',database='test') if a.native_port else None)
    if a.reference:
        native=json.loads(a.reference.read_text());assert native['result']=='PASS'
        r['different_cases']=[n for n in r['cases'] if comparable(r['cases'][n])!=comparable(native['cases'][n])]
        r['native_comparison']='FAIL' if r['different_cases'] else 'PASS'
        if r['different_cases']:r['result']='FAIL'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    if r['result']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
