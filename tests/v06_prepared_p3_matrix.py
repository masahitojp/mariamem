"""Bounded full P3 native/guest differential, isolated per scenario.

No SQL retry, packet normalization or shared-DB failure contamination.
"""
import argparse
import json
from pathlib import Path
import struct

import pymysql
from pymysql.constants import CLIENT
from v06_prepared_call_probe import CallWireError, result_chain
from v06_prepared_p1_probe import close_ping, prepare

PROC='test.prepared_p3_matrix_proc'
TABLE='test.prepared_p3_matrix_items'


def request(sid, values, reuse=False):
    header=struct.pack('<IBI',sid,0,1)
    if not values:return header
    bitmap=bytearray((len(values)+7)//8)
    for i,v in enumerate(values):
        if v is None:bitmap[i//8]|=1<<(i%8)
    return header+bitmap+bytes([not reuse])+(b'' if reuse else b'\x03\x00'*len(values))+b''.join(struct.pack('<i',v) for v in values if v is not None)


def rows(parts):return [p['rows'] for p in parts if 'columns' in p]
def introw(*values):return (b'\x00'+bytes((len(values)+9)//8)+b''.join(struct.pack('<i',v) for v in values)).hex()


def specifications():
    return {
      'zero-results':dict(args='',body='SET @p3_marker=7;',values=[],counts=[1]),
      'one-result':dict(args='',body='SELECT 17 AS v;',values=[],counts=[2]),
      'several-results':dict(args='',body="SELECT 1 AS v; SELECT _utf8mb4'日本語' AS text_value, NULL AS nil_value; SELECT CAST('123.4500' AS DECIMAL(12,4)) AS d, X'00FF' AS b;",values=[],counts=[4]),
      '129-results':dict(args='',body=''.join(f'SELECT {i} AS v;' for i in range(129)),values=[],counts=[130]),
      'IN':dict(args='IN v INT',body='SELECT v AS input_value;',values=[19],counts=[2]),
      'OUT-only':dict(args='OUT v INT',body='SET v=44;',values=[None],counts=[2],out=True),
      'INOUT-reuse':dict(args='INOUT v INT',body='SELECT v AS before_value; SET v=v+7; SELECT v AS after_value;',values=[5],second=[9],counts=[4,4],out=True),
      'IN-OUT-INOUT-reuse':dict(args='IN seed INT, OUT twice INT, INOUT total INT',body='SET twice=seed*2; SET total=total+seed; SELECT seed AS input_value;',values=[2,None,5],second=[3,None,9],counts=[3,3],out=True),
      'later-error':dict(args='',body="SELECT 101 AS before_error; SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO=1644, MESSAGE_TEXT='P3 later error'; SET @p3_after_error=1;",values=[],counts=[2],error=True),
      'initial-error':dict(args='',body="SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO=1644, MESSAGE_TEXT='P3 initial error'; SELECT 102 AS unreachable;",values=[],counts=[1],error=True),
      'metadata-change':dict(args='',body=f'SELECT * FROM {TABLE}; SELECT COUNT(*) AS n FROM {TABLE};',values=[],counts=[3,3],alter=True),
      'PS-flag-multiple':dict(args='OUT v INT',body='SELECT 11 AS first_value; SELECT 22 AS second_value; SET v=44;',values=[None],counts=[4],out=True),
      'no-PS-flag-OUT':dict(args='OUT v INT',body='SET v=44;',values=[None],counts=[1],ps=False),
      'no-PS-flag-multiple':dict(args='OUT v INT',body='SELECT 11 AS first_value; SELECT 22 AS second_value; SET v=44;',values=[None],counts=[3],ps=False),
    }


def run_case(info,name,spec,case):
    flags=CLIENT.PS_MULTI_RESULTS if spec.get('ps',True) else 0
    case['stage']='connect'
    with pymysql.connect(**info,autocommit=True,charset='utf8mb4',client_flag=flags,
                         read_timeout=10,write_timeout=10) as c:
        case['advertisement']={'server_PS_MULTI_RESULTS':bool(c.server_capabilities&CLIENT.PS_MULTI_RESULTS),
                               'client_PS_MULTI_RESULTS':bool(c.client_flag&CLIENT.PS_MULTI_RESULTS),
                               'client_MULTI_RESULTS':bool(c.client_flag&CLIENT.MULTI_RESULTS)}
        case['stage']='setup'
        with c.cursor() as q:
            q.execute('SELECT VERSION()');case['version']=q.fetchone()[0];assert case['version'].startswith('12.3.3')
            q.execute("SET NAMES utf8mb4 COLLATE utf8mb4_general_ci")
            q.execute("SET sql_mode='', time_zone='+00:00'")
            q.execute('SET @p3_after_error=0, @p3_marker=0')
            q.execute('DROP PROCEDURE IF EXISTS '+PROC)
            q.execute('DROP TABLE IF EXISTS '+TABLE)
            if spec.get('alter'):
                q.execute(f'CREATE TABLE {TABLE}(id INT PRIMARY KEY,v VARCHAR(12)) ENGINE=InnoDB')
                q.execute(f"INSERT INTO {TABLE} VALUES(1,'seed')")
            q.execute(f'CREATE PROCEDURE {PROC}({spec["args"]}) BEGIN {spec["body"]} END')
        case['stage']='prepare'
        sid,metadata=prepare(c,f'CALL {PROC}('+','.join('?' for _ in spec['values'])+')')
        case['prepare']=metadata;case['trace']=[]
        values=[spec['values']]
        if 'second' in spec:values.append(spec['second'])
        elif spec.get('alter'):values.append(spec['values'])
        for index,current in enumerate(values):
            if spec.get('alter') and index:
                with c.cursor() as q:q.execute(f'ALTER TABLE {TABLE} MODIFY v VARBINARY(12), ADD added BIGINT DEFAULT 9')
            case['stage']=f'execute/fetch/next-result/{index}'
            parts=result_chain(c,request(sid,current,reuse=index>0),allow_error=True)
            case['trace'].append(parts)
            assert len(parts)==spec['counts'][index],('result-count',len(parts),spec['counts'][index])
            if spec.get('error'):
                assert parts[-1].get('errno')==1644 and parts[-1].get('sqlstate')=='45000',parts[-1]
                assert sum('error_packet' in p for p in parts)==1
            else:
                assert all('error_packet' not in p for p in parts),parts
                assert 'ok_packet' in parts[-1] and not parts[-1]['status']&8
                assert all(p['status']&8 for p in parts[:-1])
            out_parts=[p for p in parts if p.get('status',0)&4096]
            assert len(out_parts)==int(spec.get('out',False)),('OUT-result-count',len(out_parts))
            if name=='129-results':assert rows(parts)==[[introw(i)] for i in range(129)]
            if name=='one-result':assert rows(parts)==[[introw(17)]]
            if name=='IN':assert rows(parts)==[[introw(19)]]
            if name=='OUT-only':assert rows(parts)==[[introw(44)]]
            if name=='INOUT-reuse':assert rows(parts)==[[introw(current[0])],[introw(current[0]+7)],[introw(current[0]+7)]]
            if name=='IN-OUT-INOUT-reuse':assert rows(parts)==[[introw(current[0])],[introw(current[0]*2,current[2]+current[0])]]
            if spec.get('alter'):assert len(parts[0]['columns'])==(3 if index else 2)
            case['stage']=f'following-query/{index}'
            with c.cursor() as q:
                q.execute('SELECT 1, @p3_after_error');observed=q.fetchone();assert observed==(1,0),observed
        case['stage']='close/ping';close_ping(c,sid)
        with c.cursor() as q:
            q.execute('DROP PROCEDURE '+PROC);q.execute('DROP TABLE IF EXISTS '+TABLE)
    case.update(result='PASS',following_query='PASS',close_ping='PASS');case.pop('stage',None)


def exercise(info=None,host=None,selected=None):
    result={'scope':'P3 matrix; no P4-P6 or product adoption','cases':{},'failures':{},'host_diagnostics':{}}
    for name,spec in (specifications() if selected is None else selected).items():
        case={};db=None;diag={}
        try:
            if host:
                import mariamem
                case['stage']='start';db=mariamem.start(host_binary=host);diag['runtime']=db.diagnostics;connection=db.connection_info()
            else:connection=info
            run_case(connection,name,spec,case)
        except Exception as error:
            case.update(result='FAIL',error=repr(error),errno=getattr(error,'errno',error.args[0] if isinstance(error,pymysql.MySQLError) and error.args else None),sqlstate=getattr(error,'sqlstate',None))
        finally:
            if db is not None:
                try:diag['logs']=db.logs
                except Exception as error:diag['logs_error']=repr(error)
                try:db.close()
                except Exception as error:case.update(result='FAIL',lifecycle_error=repr(error))
                try:diag['closed_logs']=db.logs
                except Exception as error:diag['closed_logs_error']=repr(error)
        result['cases'][name]=case
        if diag:result['host_diagnostics'][name]=diag
        if case.get('result')!='PASS':result['failures'][name]=case.get('error',case.get('lifecycle_error','missing PASS'))
    result['result']='FAIL' if result['failures'] else 'PASS'
    return result


def comparable(case):
    return {k:case[k] for k in ('prepare','trace','following_query','close_ping') if k in case}


def main():
    p=argparse.ArgumentParser();s=p.add_mutually_exclusive_group(required=True);s.add_argument('--native-port',type=int);s.add_argument('--host');p.add_argument('--reference',type=Path);p.add_argument('--require-advertisement',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=exercise(host=a.host) if a.host else exercise(dict(host='127.0.0.1',port=a.native_port,user='root',database='test'))
    if a.require_advertisement:
        for name,case in result['cases'].items():
            if not case.get('advertisement',{}).get('server_PS_MULTI_RESULTS'):
                result['failures'][name]='required PS_MULTI_RESULTS advertisement missing';result['result']='FAIL'
    if a.reference:
        expected=json.loads(a.reference.read_text());assert set(expected['cases'])==set(specifications()),'reference scenario inventory mismatch'
        differences=[name for name,case in result['cases'].items() if comparable(case)!=comparable(expected['cases'][name])]
        result['different_cases']=differences
        result['native_comparison']='FAIL' if differences else 'PASS'
        if differences:result['result']='FAIL'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    if result['result']!='PASS':raise SystemExit('P3 matrix FAIL; inspect per-case stages and unchanged raw native oracle')


if __name__=='__main__':main()
