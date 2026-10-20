"""P1 raw-wire/native oracle. Does not exercise or certify EXECUTE/P2-P6."""
import argparse
import json
from pathlib import Path
import struct

import pymysql
from pymysql.constants import CLIENT


def prepare(c, sql):
    c._execute_command(22, sql.encode())
    header=c._read_packet().get_all_data()
    assert len(header)==12 and header[0]==0 and header[9]==0, header.hex()
    sid,columns,params=struct.unpack_from('<IHH',header,1)
    assert sid
    groups=[]
    for count in (params,columns):
        descriptors=[c._read_packet().get_all_data().hex() for _ in range(count)]
        if count:
            eof=c._read_packet()
            assert eof.is_eof_packet(),eof.get_all_data().hex()
        groups.append(descriptors)
    return sid,dict(parameters=groups[0],columns=groups[1],warnings=int.from_bytes(header[10:12],'little'))


def close_ping(c,sid):
    # No sleeps or reads between commands: an invented CLOSE ACK or read-ahead
    # monitor consuming the PING must make this fail.
    c._execute_command(25,struct.pack('<I',sid))
    c._execute_command(14,b'')
    assert c._read_packet().is_ok_packet()


class RawErrorPacket(pymysql.protocol.MysqlPacket):
    # Retain SQLSTATE instead of letting the driver hide it in an exception.
    def is_error_packet(self):return False


def expect_error(c,op,payload,errno,state='HY000'):
    c._execute_command(op,payload)
    body=c._read_packet(RawErrorPacket).get_all_data()
    assert len(body)>=9 and body[0]==255 and body[3:4]==b'#',body.hex()
    assert int.from_bytes(body[1:3],'little')==errno,body.hex()
    assert body[4:9].decode()==state,body.hex()


def exercise(info):
    result={'scope':'P1 PREPARE/RESET/CLOSE only','checks':[],'metadata':{}}
    with pymysql.connect(**info,autocommit=True,charset='utf8mb4') as c:
        with c.cursor() as q:
            q.execute('SELECT VERSION()');version=q.fetchone()[0]
            assert version.startswith('12.3.3'),version
            result['version']=version
            q.execute('SET NAMES utf8mb4 COLLATE utf8mb4_general_ci')
            q.execute('DROP PROCEDURE IF EXISTS test.prepared_p1_proc')
            q.execute('DROP TABLE IF EXISTS test.prepared_p1_items')
            q.execute('CREATE TABLE test.prepared_p1_items(id INT PRIMARY KEY,payload VARBINARY(20)) ENGINE=InnoDB')
            q.execute('CREATE PROCEDURE test.prepared_p1_proc(IN n INT) SELECT n AS value')
        cases={
            'placeholder':'SELECT ?',
            'typed-expressions':'SELECT CAST(? AS SIGNED) AS n, CAST(? AS CHAR) AS txt',
            'dml':'INSERT INTO test.prepared_p1_items(id,payload) VALUES(?,?)',
            'call':'CALL test.prepared_p1_proc(?)',
            'zero-parameters':'SELECT 1 AS value',
            'counts65':'SELECT '+','.join('?' for _ in range(65)),
        }
        for name,sql in cases.items():
            sid,metadata=prepare(c,sql)
            result['metadata'][name]=metadata
            c._execute_command(26,struct.pack('<I',sid))
            assert c._read_packet().is_ok_packet()
            close_ping(c,sid)
            expect_error(c,26,struct.pack('<I',sid),1243)
        with c.cursor() as q:
            q.execute('SELECT COUNT(*) FROM test.prepared_p1_items');assert q.fetchone()==(0,)
        result['checks'].append('prepare-does-not-execute-dml')
        expect_error(c,22,b'SELEC broken ?',1064,'42000')
        with c.cursor() as q:
            q.execute('SELECT 1');assert q.fetchone()==(1,)
        result['checks'].append('native-1064-followed-by-query')
        # Keep more than the prototype's 64 handles alive simultaneously.
        handles=[prepare(c,'SELECT ?')[0] for _ in range(70)]
        assert len(set(handles))==70
        for sid in reversed(handles):close_ping(c,sid)
        result['checks'].append('70-live-handles-and-no-response-close-ping')
        # A fresh physical connection cannot resolve this connection's ID.
        sid,_=prepare(c,'SELECT ?')
        with pymysql.connect(**info,autocommit=True) as other:
            expect_error(other,26,struct.pack('<I',sid),1243)
            close_ping(other,sid)  # unknown CLOSE has no response either
        close_ping(c,sid)
        result['checks'].append('cross-session-unknown-id')
        with c.cursor() as q:q.execute('START TRANSACTION')
        c._execute_command(25,struct.pack('<I',0))
        c._execute_command(14,b'')
        ping=pymysql.protocol.OKPacketWrapper(c._read_packet())
        assert ping.server_status & 1,'ignored CLOSE lost the active text transaction'
        with c.cursor() as q:q.execute('ROLLBACK')
        result['checks'].append('unknown-close-preserves-text-transaction-status')
    # FOUND_ROWS reopens MYSQL after the greeting. The final open generation
    # must be used; binding the initial generation rejects this real operation.
    with pymysql.connect(**info,autocommit=True,client_flag=CLIENT.FOUND_ROWS) as found:
        sid,_=prepare(found,'SELECT ?')
        found._execute_command(26,struct.pack('<I',sid));assert found._read_packet().is_ok_packet()
        close_ping(found,sid)
    result['checks'].append('found-rows-final-session-generation')
    result['result']='PASS'
    return result


def main():
    p=argparse.ArgumentParser();source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--host');source.add_argument('--native-port',type=int)
    p.add_argument('--reference',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result={'result':'FAIL','scope':'P1 only'}
    try:
        if a.host:
            import mariamem
            with mariamem.start(host_binary=a.host) as db:
                result=exercise(db.connection_info())
        else:
            result=exercise(dict(host='127.0.0.1',port=a.native_port,user='root',database='test'))
        if a.reference:
            expected=json.loads(a.reference.read_text())
            assert result['metadata']==expected['metadata'],'actual PREPARE metadata differs from pinned native control'
            result['native_metadata']='PASS'
    except Exception as error:
        result.update(result='FAIL',error=repr(error))
        raise
    finally:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
