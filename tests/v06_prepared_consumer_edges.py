"""Diagnostic captures. A completed capture is not a functional PASS."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import platform
import ssl
import sys


def error(e):
    return {'type':type(e).__name__,'errno':getattr(e,'errno',None),'sqlstate':getattr(e,'sqlstate',None),'message':str(e)}


def value(v):
    return {'bytes_hex':bytes(v).hex()} if isinstance(v,(bytes,bytearray)) else v


def capture(info,mode):
    import mysql.connector as connector
    kw={} if mode=='default' else {'use_pure':mode=='pure'}
    result={'mode':mode,'cases':{}}
    if mode=='cext' and not connector.HAVE_CEXT:
        return {'mode':mode,'capture':'SKIP','reason':'explicit C extension unavailable'}
    connect=lambda:connector.connect(**info,connection_timeout=5,read_timeout=10,write_timeout=10,**kw)
    with connect() as c:
        result['implementation']=type(c).__name__
        with c.cursor(prepared=True) as q:
            q.execute('SELECT %s, HEX(%s), OCTET_LENGTH(%s), CAST(%s AS BINARY)',(b'A\0B',)*4)
            row=q.fetchone();assert row is not None;q.fetchall()
            got=[value(v) for v in row]
            result['cases']['nul_projection']={'row':got,'functional_result':'PASS' if got==['A\0B','410042',3,{'bytes_hex':'410042'}] else 'FAIL'}
    c=connect();q=None;call={'stage':'setup','resultsets':[],'cleanup_errors':[]}
    try:
        with c.cursor() as setup:
            setup.execute('DROP PROCEDURE IF EXISTS test.p5_edge_call')
            setup.execute('CREATE PROCEDURE test.p5_edge_call(IN x INT) BEGIN SELECT x; SELECT x+1; END')
        q=c.cursor(prepared=True)
        call['nextset_owner']=q.nextset.__func__.__qualname__
        call['nextset_source_sha256']=hashlib.sha256(inspect.getsource(q.nextset.__func__).encode()).hexdigest()
        call['stage']='execute';q.execute('CALL test.p5_edge_call(%s)',(7,))
        while True:
            call['stage']='fetchall'
            if q.with_rows:call['resultsets'].append([[value(v) for v in row] for row in q.fetchall()])
            call['stage']='nextset'
            if not q.nextset():break
        call['functional_result']='PASS' if call['resultsets']==[[[7]],[[8]]] else 'FAIL'
    except Exception as e:call.update(functional_result='FAIL',error=error(e))
    # Preserve the primary failure separately from cleanup or following-query
    # errors; never infer connection health from a cursor's close exception.
    try:
        with c.cursor() as following:
            following.execute('SELECT 1');call['following_query']=[list(row) for row in following.fetchall()]
    except Exception as e:call['following_query_error']=error(e)
    finally:
        if q:
            try:q.close()
            except Exception as e:call['cleanup_errors'].append(error(e))
        try:c.close()
        except Exception as e:call['cleanup_errors'].append(error(e))
    result['cases']['prepared_call']=call;result['capture']='COMPLETE'
    return result


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--native-port',type=int);g.add_argument('--host',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    import mysql.connector as connector
    assert connector.__version__=='26.7.0'
    r={'scope':'consumer edge characterization, never adoption acceptance','environment':{'connector':connector.__version__,'python':sys.version,'openssl':ssl.OPENSSL_VERSION,'system':platform.system(),'architecture':platform.machine()},'modes':{}}
    for mode in ('pure','default','cext'):
        db=None
        try:
            if a.host:
                import mariamem
                db=mariamem.start(host_binary=str(a.host));info=db.connection_info()
            else:info=dict(host='127.0.0.1',port=a.native_port,user='root',database='test')
            r['modes'][mode]=capture(info,mode)
        except Exception as e:r['modes'][mode]={'capture':'FAIL','error':error(e)}
        finally:
            if db:db.close()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    if any(v['capture']=='FAIL' for v in r['modes'].values()):raise SystemExit(1)

if __name__=='__main__':main()
