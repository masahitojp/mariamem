"""P3 first CALL case; compare complete packets, not just selected rows."""
import argparse
import json
from pathlib import Path
import struct

import pymysql
from pymysql.constants import CLIENT
from v06_prepared_p1_probe import RawErrorPacket, close_ping, prepare


class CallWireError(Exception):
    def __init__(self, stage, raw):
        assert len(raw)>=9 and raw[3:4]==b'#',raw.hex()
        self.errno=int.from_bytes(raw[1:3],'little')
        self.sqlstate=raw[4:9].decode() if raw[3:4]==b'#' else None
        super().__init__(stage,self.errno,self.sqlstate,raw.hex())


def result_chain(c, payload, allow_error=False):
    c._execute_command(23, payload)
    results=[]
    while True:
        first=c._read_packet(RawErrorPacket)
        raw=first.get_all_data()
        if raw[0]==255:
            error=CallWireError(f'next-result/{len(results)}',raw)
            if not allow_error:raise error
            results.append({'error_packet':raw.hex(),'errno':error.errno,'sqlstate':error.sqlstate})
            break
        if first.is_ok_packet():
            first.read_uint8()
            first.read_length_encoded_integer();first.read_length_encoded_integer()
            status=first.read_uint16()
            results.append({'ok_packet':raw.hex(),'status':status})
        else:
            count=first.read_length_encoded_integer()
            columns=[c._read_packet().get_all_data().hex() for _ in range(count)]
            meta=c._read_packet();assert meta.is_eof_packet(),meta.get_all_data().hex()
            rows=[]
            while True:
                row=c._read_packet(RawErrorPacket)
                data=row.get_all_data()
                if data[0]==255:
                    error=CallWireError(f'fetch/{len(results)}',data)
                    if not allow_error:raise error
                    results.append({'columns':columns,'metadata_end':meta.get_all_data().hex(),
                                    'rows':rows,'error_packet':data.hex(),'errno':error.errno,'sqlstate':error.sqlstate})
                    return results
                if row.is_eof_packet():break
                assert data[0]==0,data.hex()
                rows.append(data.hex())
            status=int.from_bytes(data[3:5],'little')
            results.append({'columns':columns,'metadata_end':meta.get_all_data().hex(),
                            'rows':rows,'terminal':data.hex(),'status':status})
        if not status&8:break
    return results


def exercise(info):
    stage='connect'
    result={'scope':'P3 minimal one OUT plus two ordinary results only','result':'FAIL'}
    try:
        # Experimental probe deliberately requests PS results. Product advertisement
        # remains gated until the complete P3 matrix, not enabled by this one case.
        with pymysql.connect(**info,autocommit=True,charset='utf8mb4',client_flag=CLIENT.PS_MULTI_RESULTS,
                             read_timeout=10,write_timeout=10) as c:
            result['server_ps_multi_results_advertised']=bool(c.server_capabilities&CLIENT.PS_MULTI_RESULTS)
            stage='setup'
            with c.cursor() as q:
                q.execute('SELECT VERSION()');result['version']=q.fetchone()[0]
                assert result['version'].startswith('12.3.3')
                q.execute("SET NAMES utf8mb4 COLLATE utf8mb4_general_ci")
                q.execute("SET sql_mode='', time_zone='+00:00'")
                q.execute('DROP PROCEDURE IF EXISTS test.prepared_p3_minimal')
                q.execute('CREATE PROCEDURE test.prepared_p3_minimal(OUT v INT) BEGIN '
                          'SELECT 11 AS first_value; SELECT 22 AS second_value, 33 AS extra_value; SET v=44; END')
            stage='prepare';sid,meta=prepare(c,'CALL test.prepared_p3_minimal(?)')
            result['prepare']=meta
            stage='execute/fetch/next-result'
            payload=struct.pack('<IBI',sid,0,1)+b'\x01\x01\x03\x00'  # one NULL INT OUT argument
            chain=result_chain(c,payload);result['results']=chain
            assert len(chain)==4,chain
            assert [len(x.get('columns',[])) for x in chain]==[1,2,1,0]
            assert chain[0]['rows']==['00000b000000']
            assert chain[1]['rows']==['00001600000021000000']
            assert chain[2]['rows']==['00002c000000']
            assert not chain[0]['status']&4096 and not chain[1]['status']&4096
            assert chain[2]['status']&4096 and all(x['status']&8 for x in chain[:-1])
            assert 'ok_packet' in chain[-1] and not chain[-1]['status']&8
            stage='following-select'
            with c.cursor() as q:q.execute('SELECT 1');assert q.fetchone()==(1,)
            close_ping(c,sid)
            with c.cursor() as q:q.execute('DROP PROCEDURE test.prepared_p3_minimal')
        result.update(result='PASS',following_select='PASS',close_ping='PASS')
        return result
    except Exception as error:
        result.update(stage=stage,error=repr(error),errno=getattr(error,'errno',error.args[0] if isinstance(error,pymysql.MySQLError) and error.args else None),sqlstate=getattr(error,'sqlstate',None))
        raise
    finally:
        exercise.last_result=result


def main():
    p=argparse.ArgumentParser();s=p.add_mutually_exclusive_group(required=True)
    s.add_argument('--native-port',type=int);s.add_argument('--host');p.add_argument('--reference',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result={'result':'FAIL'};diagnostics={}
    try:
        if a.host:
            import mariamem
            db=mariamem.start(host_binary=a.host)
            diagnostics['runtime']=db.diagnostics
            try:result=exercise(db.connection_info())
            finally:
                try:diagnostics['logs']=db.logs
                except Exception as error:diagnostics['logs_error']=repr(error)
                db.close()
                try:diagnostics['closed_logs']=db.logs
                except Exception as error:diagnostics['closed_logs_error']=repr(error)
        else:result=exercise(dict(host='127.0.0.1',port=a.native_port,user='root',database='test'))
        if a.reference:
            ref=json.loads(a.reference.read_text())
            for key in ('prepare','results'):assert result[key]==ref[key],f'P3 minimal {key} differs from native'
            result['native_comparison']='PASS'
    except Exception as error:
        result=getattr(exercise,'last_result',result)
        result.update(result='FAIL',error=repr(error),stage=result.get('stage','native-comparison'))
        raise
    finally:
        if a.host:result['host_diagnostics']=diagnostics
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
