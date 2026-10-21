"""P2 DML/schema/type differential; retain independent scenario failures.

Rows compare complete descriptor/binary/terminal bytes. DML compares affected
rows, insert ID, status and warning count. OK informational text is retained as
separate observations, not a promised exact-parity field in this matrix.
"""
import argparse
import json
from pathlib import Path
import struct

import pymysql
from v06_prepared_p1_probe import RawErrorPacket, close_ping, prepare


FIXED={1:1,2:2,13:2,3:4,9:4,4:4,8:8,5:8}
TEMPORAL={7,10,11,12,14}


def length_encoded(data):
    n=len(data)
    if n<251:return bytes([n])+data
    if n<=65535:return b'\xfc'+struct.pack('<H',n)+data
    raise ValueError('fixture field too long')


def payload(sid,values,reuse=False):
    bitmap=bytearray((len(values)+7)//8)
    body=bytearray();types=bytearray()
    for i,(typ,unsigned,value) in enumerate(values):
        types+=bytes([typ,128 if unsigned else 0])
        if value is None:
            bitmap[i//8]|=1<<(i%8)
        elif typ in FIXED:
            assert len(value)==FIXED[typ];body+=value
        elif typ in TEMPORAL:
            body+=bytes([len(value)])+value
        else:body+=length_encoded(value)
    return (struct.pack('<IBI',sid,0,1) if not values else
            struct.pack('<IBI',sid,0,1)+bitmap+bytes([not reuse])+
            (b'' if reuse else types)+body)


def execute(c,sid,values,diagnostics,reuse=False):
    c._execute_command(23,payload(sid,values,reuse))
    packet=c._read_packet(RawErrorPacket);raw=packet.get_all_data()
    if raw[0]==255:
        assert len(raw)>=9 and raw[3:4]==b'#'
        return {'kind':'error','errno':int.from_bytes(raw[1:3],'little'),
                'sqlstate':raw[4:9].decode(),'message_hex':raw[9:].hex()}
    if packet.is_ok_packet():
        assert packet.read_uint8()==0
        affected=packet.read_length_encoded_integer();insert_id=packet.read_length_encoded_integer()
        status,warnings=packet.read_struct('<HH')
        diagnostics.append({'ok_info_hex':packet.read_all().hex(),'ok_packet_hex':raw.hex()})
        return dict(kind='ok',affected=affected,insert_id=insert_id,status=status,warnings=warnings)
    count=packet.read_length_encoded_integer()
    columns=[c._read_packet().get_all_data().hex() for _ in range(count)]
    assert c._read_packet().is_eof_packet()
    rows=[]
    while True:
        packet=c._read_packet()
        if packet.is_eof_packet():break
        row=packet.get_all_data();assert row[0]==0;rows.append(row.hex())
    return dict(kind='rows',columns=columns,rows=rows,terminal=packet.get_all_data().hex())


def query(c,sql):
    with c.cursor() as q:q.execute(sql);return q.fetchall()


def run_group(info,scenario):
    result={'trace':[],'ok_observations':[]}
    try:
        with pymysql.connect(**info,autocommit=True,charset='utf8mb4',read_timeout=10,write_timeout=10) as c:
            assert query(c,'SELECT VERSION()')[0][0].startswith('12.3.3')
            query(c,'SET NAMES utf8mb4 COLLATE utf8mb4_general_ci')
            query(c,"SET sql_mode='', time_zone='+00:00'")
            def call(sid,values=(),reuse=False):
                reply=execute(c,sid,values,result['ok_observations'],reuse)
                result['trace'].append(reply);return reply
            try:scenario(c,call)
            except Exception as error:
                result['failure']=dict(type=type(error).__name__,error=str(error))
            try:
                assert query(c,'SELECT 1')==((1,),)
                result['healthy_following_query']=True
            except Exception as error:
                result['healthy_following_query']=False
                result['following_query_failure']=dict(type=type(error).__name__,error=str(error))
                result.setdefault('failure',result['following_query_failure'])
    except Exception as error:
        result.setdefault('failure',dict(type=type(error).__name__,error=str(error)))
    return result


def parameter(typ,value,unsigned=False):
    def scenario(c,call):
        sid,_=prepare(c,'SELECT ? AS v')
        first=call(sid,[(typ,unsigned,value)])
        assert call(sid,[(typ,unsigned,value)],True)==first
        close_ping(c,sid)
    return scenario


def type_changes(c,call):
    sid,_=prepare(c,'SELECT ? AS v')
    for value in [(3,False,struct.pack('<i',-7)),(8,True,b'\xff'*8),
                  (253,False,'日本語'.encode()),(253,False,b''),(253,False,None),
                  (246,False,b'123.4500'),(3,False,struct.pack('<i',9))]:
        call(sid,[value])
    close_ping(c,sid)


def dml(c,call):
    query(c,'CREATE TEMPORARY TABLE p2_matrix_items(id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,v VARCHAR(3)) ENGINE=InnoDB')
    sid,_=prepare(c,'INSERT INTO p2_matrix_items(v) VALUES(?)')
    for value in [b'abc',b'abc',b'abcdef']:
        reply=call(sid,[(253,False,value)]);assert reply['kind']=='ok'
    close_ping(c,sid)
    sid,_=prepare(c,'UPDATE p2_matrix_items SET v=? WHERE id=?')
    for value in [b'xyz',b'xyz']:
        assert call(sid,[(253,False,value),(8,True,struct.pack('<Q',1))])['kind']=='ok'
    close_ping(c,sid)
    sid,_=prepare(c,'INSERT INTO p2_matrix_items(id,v) VALUES(?,?)')
    reply=call(sid,[(8,True,struct.pack('<Q',1)),(253,False,b'bad')])
    assert reply['kind']=='error' and reply['errno']==1062 and reply['sqlstate']=='23000'
    assert call(sid,[(8,True,struct.pack('<Q',8)),(253,False,b'ok')])['kind']=='ok'
    close_ping(c,sid)
    sid,_=prepare(c,'SELECT id,v FROM p2_matrix_items ORDER BY id');call(sid);close_ping(c,sid)


def transactions(c,call):
    query(c,'CREATE TEMPORARY TABLE p2_matrix_tx(v INT) ENGINE=InnoDB')
    sid,_=prepare(c,'INSERT INTO p2_matrix_tx VALUES(?)')
    query(c,'START TRANSACTION');call(sid,[(3,False,struct.pack('<i',1))]);query(c,'ROLLBACK')
    query(c,'START TRANSACTION');call(sid,[(3,False,struct.pack('<i',2))],True);query(c,'COMMIT')
    close_ping(c,sid)
    sid,_=prepare(c,'SELECT v FROM p2_matrix_tx');call(sid);close_ping(c,sid)


def schema(change):
    def scenario(c,call):
        query(c,'CREATE TEMPORARY TABLE p2_matrix_schema(v INT,other_col INT) ENGINE=InnoDB')
        query(c,'INSERT INTO p2_matrix_schema VALUES(7,9)')
        sid,_=prepare(c,'SELECT * FROM p2_matrix_schema' if change=='add' else 'SELECT v FROM p2_matrix_schema')
        call(sid)
        query(c,{'type':'ALTER TABLE p2_matrix_schema MODIFY v BIGINT',
                 'add':'ALTER TABLE p2_matrix_schema ADD COLUMN new_col INT DEFAULT 11',
                 'drop':'ALTER TABLE p2_matrix_schema DROP COLUMN v'}[change])
        reply=call(sid)
        if change=='drop':assert reply['kind']=='error' and reply['errno']==1054
        else:assert reply['kind']=='rows'
        close_ping(c,sid)
    return scenario


def date_modes(c,call):
    query(c,'CREATE TEMPORARY TABLE p2_matrix_dates(v DATE) ENGINE=InnoDB')
    sid,_=prepare(c,'INSERT INTO p2_matrix_dates VALUES(?)')
    for mode in ['', 'STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE']:
        query(c,"SET sql_mode='"+mode+"'")
        for value in [b'',struct.pack('<HBB',2024,2,29),struct.pack('<HBB',2024,13,1)]:
            call(sid,[(10,False,value)])
    close_ping(c,sid)
    query(c,"SET sql_mode=''")
    sid,_=prepare(c,'SELECT v FROM p2_matrix_dates ORDER BY v');call(sid);close_ping(c,sid)


def scenarios():
    values={0:b'123.4500',15:b'text',16:b'\x01',247:b'alpha',248:b'alpha',
            249:b'\0\xff',250:b'\0\xff',251:b'\0\xff',255:b'\0\xff',
            9:struct.pack('<i',-8388608),13:struct.pack('<H',2024),
            14:struct.pack('<HBB',2024,2,29),7:struct.pack('<HBBBBBI',2024,2,29,12,34,56,123456)}
    result={f'parameter-type-{typ}':parameter(typ,value) for typ,value in values.items()}
    result.update({'repeated-type-changes':type_changes,'dml-warnings-recovery':dml,
                   'commit-rollback':transactions,'date-sql-modes':date_modes})
    result.update({f'schema-{change}':schema(change) for change in ['type','add','drop']})
    return result


def exercise(info):
    result={'scope':'additional P2 DML/schema/types/modes; not full P2-P6','cases':{},'failures':{}}
    for name,scenario in scenarios().items():
        case=run_group(info,scenario)
        result['cases'][name]=case
        if 'failure' in case:result['failures'][name]=case['failure']
    result['result']='FAIL' if result['failures'] else 'PASS'
    return result


def comparable(cases):
    return {name:{k:v for k,v in case.items() if k!='ok_observations'} for name,case in cases.items()}


def main():
    p=argparse.ArgumentParser();s=p.add_mutually_exclusive_group(required=True)
    s.add_argument('--native-port',type=int);s.add_argument('--host')
    p.add_argument('--reference',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result={'result':'FAIL'}
    try:
        if args.host:
            import mariamem
            with mariamem.start(host_binary=args.host) as db:result=exercise(db.connection_info())
        else:result=exercise(dict(host='127.0.0.1',port=args.native_port,user='root',database='test'))
        if args.reference:
            expected=json.loads(args.reference.read_text())
            observed,wanted=comparable(result['cases']),comparable(expected['cases'])
            result['different_cases']=[name for name in sorted(set(observed)|set(wanted)) if observed.get(name)!=wanted.get(name)]
            result['native_comparison']='FAIL' if result['different_cases'] or result['failures'] else 'PASS'
            if result['native_comparison']=='FAIL':result['result']='FAIL'
        assert result['result']=='PASS',json.dumps({k:result.get(k) for k in ['failures','different_cases']})
    except Exception as error:
        result.update(result='FAIL',error=repr(error));raise
    finally:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
