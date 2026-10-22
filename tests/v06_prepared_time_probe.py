"""Bounded TIME metadata/value differential; no exception normalization."""
import argparse
import json
from pathlib import Path
import struct

import pymysql
from v06_prepared_p1_probe import close_ping, prepare
from v06_prepared_p2_probe import execute


def time_value(negative=False,days=0,hours=0,minutes=0,seconds=0,microseconds=None):
    body=struct.pack('<BIBBB',negative,days,hours,minutes,seconds)
    return body if microseconds is None else body+struct.pack('<I',microseconds)


def request(sid,values,reuse=False):
    return (struct.pack('<IBI',sid,0,1)+bytes((len(values)+7)//8)+bytes([not reuse])+
            (b'' if reuse else b'\x0b\0'*len(values))+
            b''.join(bytes([len(v)])+v for v in values))


def exercise(info):
    cases={}
    values=[('zero-empty',b''),('zero-components',time_value()),
            ('no-fraction',time_value(hours=12,minutes=34,seconds=56)),
            ('fraction',time_value(hours=12,microseconds=123456)),
            ('negative',time_value(True,hours=12,microseconds=123456)),
            ('over-24h',time_value(days=2,hours=3)),
            ('max-whole',time_value(days=34,hours=22,minutes=59,seconds=59)),
            ('max-fraction',time_value(days=34,hours=22,minutes=59,seconds=59,microseconds=999999)),
            ('over-range',time_value(days=34,hours=23,microseconds=123456))]
    with pymysql.connect(**info,autocommit=True,charset='utf8mb4',read_timeout=10,write_timeout=10) as c:
        with c.cursor() as q:
            q.execute('SELECT VERSION()');version=q.fetchone()[0]
            assert version.startswith('12.3.3'),version
            q.execute("SET NAMES utf8mb4 COLLATE utf8mb4_general_ci")
            q.execute("SET sql_mode='', time_zone='+00:00'")
            q.execute('CREATE TEMPORARY TABLE prepared_time_metadata (v TIME(6))')
            q.execute("INSERT INTO prepared_time_metadata VALUES ('-51:04:05.654321')")
        for name,value in values:
            sid,_=prepare(c,'SELECT ? AS v')
            cases[name]=execute(c,request(sid,[value]))
            assert execute(c,request(sid,[value],True))==cases[name],name
            close_ping(c,sid)
        extra=[('cast-expression','SELECT CAST(? AS TIME(6)) AS v',[values[4][1]]),
               ('time-field','SELECT v FROM prepared_time_metadata',[]),
               ('field-and-parameter','SELECT v, ? AS p FROM prepared_time_metadata',[values[4][1]]),
               ('two-parameters','SELECT ? AS a, ? AS b',[values[2][1],values[4][1]])]
        for name,sql,parameters in extra:
            sid,_=prepare(c,sql)
            payload=request(sid,parameters) if parameters else struct.pack('<IBI',sid,0,1)
            cases[name]=execute(c,payload)
            close_ping(c,sid)
        with c.cursor() as q:
            q.execute('SELECT 1');assert q.fetchone()==(1,)
    return {'version':version,'scope':'bounded TIME width repair, not full P2-P6','cases':cases,'result':'PASS'}


def main():
    p=argparse.ArgumentParser()
    s=p.add_mutually_exclusive_group(required=True)
    s.add_argument('--native-port',type=int);s.add_argument('--host')
    p.add_argument('--reference',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result={'result':'FAIL'}
    try:
        if args.host:
            import mariamem
            with mariamem.start(host_binary=args.host) as db:result=exercise(db.connection_info())
        else:result=exercise(dict(host='127.0.0.1',port=args.native_port,user='root',database='test'))
        if args.reference:
            assert result['cases']==json.loads(args.reference.read_text())['cases'],'TIME raw results differ from native'
            result['native_comparison']='PASS'
    except Exception as error:
        result.update(result='FAIL',error=repr(error));raise
    finally:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
