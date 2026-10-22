"""P4 active EXECUTE exits: native controls and existing fatal-DB contract.

A named lock acquired by the procedure is an execution witness. No sleep is
used to guess that the query started. Native connection survival and product
DB invalidation are checked separately, never normalized into wire equivalence.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import socket
import struct
import subprocess
import threading
import time

import pymysql
from v06_prepared_call_probe import result_chain
from v06_prepared_p1_probe import close_ping,prepare
from v06_prepared_p2_matrix import payload,query

COMMON=('ordinary-error','go-cancel','go-deadline','active-eof','active-reset')
PRODUCT_ONLY=('host-deadline','active-db-close')
MARKER='mariamem-p4-active-witness'


def connect(info):return pymysql.connect(**info,autocommit=True,charset='utf8mb4',read_timeout=15,write_timeout=15)


def setup(info):
    with connect(info) as c:
        assert query(c,'SELECT VERSION()')[0][0].startswith('12.3.3')
        query(c,'DROP PROCEDURE IF EXISTS test.p4_active')
        query(c,'DROP TABLE IF EXISTS test.p4_active_rows')
        query(c,'CREATE TABLE test.p4_active_rows(id INT PRIMARY KEY,v INT) ENGINE=InnoDB')
        query(c,'INSERT INTO test.p4_active_rows VALUES(1,7)')
        query(c,"CREATE PROCEDURE test.p4_active(IN delay_seconds INT) BEGIN "
              "IF delay_seconds<0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='p4 ordinary control'; END IF; "
              "UPDATE test.p4_active_rows SET v=99 WHERE id=1; "
              f"DO GET_LOCK('{MARKER}',0); DO SLEEP(delay_seconds); "
              f"DO RELEASE_LOCK('{MARKER}'); END")


def witness(c,actor_id,pending):
    end=time.monotonic()+2
    while time.monotonic()<end:
        owner=query(c,f"SELECT IS_USED_LOCK('{MARKER}')")[0][0]
        if owner==actor_id:
            assert pending(),'actor finished before controller action'
            assert query(c,'SELECT v FROM test.p4_active_rows')==((7,),),'uncommitted write became visible'
            return {'actor_id':actor_id,'lock_owner':owner,'uncommitted_write_hidden':True}
        assert pending(),'EXECUTE ended before an execution witness'
        time.sleep(.005)  # bounded observation, not a presumed start delay
    raise AssertionError('active SQL witness not observed; do not claim cancellation coverage')


def native_drained(c):
    end=time.monotonic()+10
    while time.monotonic()<end:
        n=int(query(c,"SHOW GLOBAL STATUS LIKE 'Prepared_stmt_count'")[0][1])
        owner=query(c,f"SELECT IS_USED_LOCK('{MARKER}')")[0][0]
        if n==0 and owner is None:
            assert query(c,'SELECT v FROM test.p4_active_rows')==((7,),)
            return {'prepared_after':0,'named_lock_released':True,'baseline_value':7,'other_connection_usable':True}
        time.sleep(.01)
    raise AssertionError(('native resources not drained',n,owner))


def go_exit(info,observer,kind,consumer,out):
    env=dict(os.environ,MARIAMEM_P4_ACTIVE_KIND=kind,
             MARIAMEM_P4_ACTIVE_DSN=f"{info['user']}:{info.get('password','')}@tcp({info['host']}:{info['port']})/{info.get('database','test')}?timeout=5s&readTimeout=15s&writeTimeout=15s")
    p=subprocess.Popen([str(consumer)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    events=queue.Queue();captured=[]
    def read():
        try:
            for line in p.stdout:events.put(json.loads(line))
        except Exception as e:events.put({'phase':'reader-error','error':repr(e)})
    reader=threading.Thread(target=read,daemon=True);reader.start()
    try:
        ready=events.get(timeout=10);captured.append(ready);assert ready['phase']=='prepared',ready
        sent=events.get(timeout=10);captured.append(sent);assert sent['phase']=='submitted',sent
        out['witness']=witness(observer,ready['connection_id'],lambda:p.poll() is None)
        p.stdin.write(kind+'\n' if kind in ('cancel','reset') else 'observe\n');p.stdin.flush()
        finished=events.get(timeout=15);captured.append(finished)
        assert p.wait(timeout=5)==0 and finished['phase']=='finished' and finished['result']=='PASS',finished
        assert finished['open_after']==0 and finished['execute_error']
        if kind=='reset':assert finished['transport_failed']
        out['consumer']=finished
    finally:
        if p.poll() is None:p.kill();p.wait(timeout=5)
        reader.join(timeout=2);out['consumer_events']=captured;out['consumer_stderr']=p.stderr.read()


def raw_exit(info,observer,mode,db,out):
    c=connect(info);completed={}
    try:
        actor_id=int(query(c,'SELECT CONNECTION_ID()')[0][0]);query(c,'START TRANSACTION')
        sid,meta=prepare(c,'CALL test.p4_active(?)');out['prepare']=meta
        def execute():
            try:completed['packets']=result_chain(c,payload(sid,[(3,False,struct.pack('<i',5))]),allow_error=True)
            except Exception as e:completed['error']=repr(e)
        thread=threading.Thread(target=execute,daemon=True);thread.start()
        out['witness']=witness(observer,actor_id,thread.is_alive)
        if mode=='active-eof':c._sock.shutdown(socket.SHUT_RDWR);c._force_close()
        elif mode=='active-db-close':db.close();db.close()
        elif mode!='host-deadline':raise ValueError(mode)
        thread.join(timeout=15);assert not thread.is_alive(),'active reader did not finish'
        out['execution_outcome']=completed
        assert completed.get('error') or any('errno' in p for p in completed.get('packets',[])),'interrupted EXECUTE returned success'
    finally:c._force_close()


def fatal_state(db,info):
    import mariamem
    end=time.monotonic()+10
    while time.monotonic()<end:
        try:db.status()
        except mariamem.HostError as e:
            assert e.code=='unusable' and e.closed,(e.code,e.closed,str(e))
            result={'code':e.code,'closed':e.closed,'message':str(e)};break
        time.sleep(.01)
    else:raise AssertionError('active cancellation failed to invalidate the target DB')
    # Use saved coordinates; don't substitute a wrapper-only connection_info error.
    try:
        with connect(info) as replacement:query(replacement,'SELECT 1')
    except (pymysql.MySQLError,OSError):result['new_SQL_admission_rejected']=True
    else:raise AssertionError('failed DB admitted a new usable connection')
    return result


def case(info,name,consumer,out,db=None):
    with connect(info) as observer:
        assert query(observer,'SELECT v FROM test.p4_active_rows')==((7,),)
        if name=='ordinary-error':
            sid,meta=prepare(observer,'CALL test.p4_active(?)');out['prepare']=meta
            chain=result_chain(observer,payload(sid,[(3,False,struct.pack('<i',-1))]),allow_error=True)
            assert chain[0]['errno']==1644 and chain[0]['sqlstate']=='45000';out['error_packets']=chain
            assert query(observer,'SELECT 1')==((1,),);close_ping(observer,sid)
            assert query(observer,'SELECT v FROM test.p4_active_rows')==((7,),)
            out['ordinary_SQL_error_keeps_DB_usable']=True
        elif name.startswith('go-'):go_exit(info,observer,name[3:],consumer,out)
        elif name=='active-reset':go_exit(info,observer,'reset',consumer,out)
        else:raw_exit(info,observer,name,db,out)
        if db is None:
            out['native_cleanup']=native_drained(observer)
            out['native_cleanup']['transaction_rollback_checked']=name!='ordinary-error'
    if db is not None:
        if name not in ('ordinary-error','active-db-close'):
            out['fatal_DB']=fatal_state(db,info)
            if name=='host-deadline':assert 'deadline exceeded' in out['fatal_DB']['message']
        elif name=='active-db-close':
            assert db.closed
            try:
                with connect(info) as replacement:query(replacement,'SELECT 1')
            except (pymysql.MySQLError,OSError):out['explicit_Close_new_SQL_rejected']=True
            else:raise AssertionError('closed DB admitted usable SQL')
        else:
            with connect(info) as c:
                assert query(c,'SELECT 1')==((1,),)
                out['ordinary_prepared_after']=int(query(c,"SHOW GLOBAL STATUS LIKE 'Prepared_stmt_count'")[0][1]);assert out['ordinary_prepared_after']==0
            assert not db.closed
    out['result']='PASS'


def exercise(consumer,native_port=None,host=None):
    r={'scope':'P4 active EXECUTE exits only; not full P4/P5/P6','cases':{},'failures':{}}
    for name in COMMON+(PRODUCT_ONLY if host else ()):
        out={'stage':'setup'};db=None;baseline=None;healthy=None;source=None;lineage_root=None
        try:
            if host:
                import mariamem
                source=mariamem.start(host_binary=host,query_timeout=2 if name=='host-deadline' else 15)
                setup(source.connection_info());source.wait_disconnected(timeout=10)
                baseline=source.snapshot();db=baseline.fork();healthy=baseline.fork();info=db.connection_info();lineage_root=db.log_path.parent
                with connect(healthy.connection_info()) as c:assert query(c,'SELECT v FROM test.p4_active_rows')==((7,),)
            else:
                info=dict(host='127.0.0.1',port=native_port,user='root',database='test');setup(info)
            out['stage']='execute-and-exit'
            case(info,name,consumer,out,db)
            if db:
                out['cleanup_counter_limit']='fatal DB cases cannot expose Prepared_stmt_count; native count is checked separately'
                out['stage']='target-close'
                target_log=db.log_path;out['target_logs']=db.logs;db.close();db.close();assert not target_log.exists();assert lineage_root.exists();out['target_log_removed']=True;out['shared_lineage_retained_while_baseline_alive']=True
                out['stage']='sibling-after-exit'
                with connect(healthy.connection_info()) as c:assert query(c,'SELECT v FROM test.p4_active_rows')==((7,),)
                healthy.wait_disconnected(timeout=10);out['sibling_usable_and_unchanged']=True
                out['stage']='baseline-reuse'
                with baseline.fork() as recovered:
                    with connect(recovered.connection_info()) as c:
                        sid,_=prepare(c,'SELECT ?');chain=result_chain(c,payload(sid,[(3,False,struct.pack('<i',7))]));assert chain[0]['rows']==['000007000000'];close_ping(c,sid)
                    recovered.wait_disconnected(timeout=10)
                out['baseline_reusable_with_prepared_QUERY']=True
        except Exception as e:out.update(result='FAIL',error=repr(e))
        finally:
            if db and 'target_logs' not in out:
                try:out['target_logs']=db.logs
                except Exception as e:
                    out['target_log_error']=repr(e)
                    if db.log_path.exists():out['target_logs']=db.log_path.read_text(errors='replace')[-16384:]
            for resource in (db,healthy,baseline,source):
                if resource:
                    try:resource.close()
                    except Exception as e:out.update(result='FAIL',cleanup_error=repr(e))
        if lineage_root is not None:
            if lineage_root.exists():out.update(result='FAIL',cleanup_error='lineage temp retained after all owners closed')
            else:out['lineage_temporary_removed']=True
        if out.get('result')=='PASS':out.pop('stage',None)
        r['cases'][name]=out
        if out.get('result')!='PASS':r['failures'][name]=out.get('error',out.get('cleanup_error','missing result'))
    r['result']='FAIL' if r['failures'] else 'PASS';return r



def validate_reference(r,native):
    assert native['result']=='PASS' and not native['failures']
    assert set(native['cases'])==set(COMMON)
    assert set(r['cases'])==set(COMMON+PRODUCT_ONLY)
    for name in COMMON:
        n=native['cases'][name];c=r['cases'][name]
        assert n['native_cleanup']=={'prepared_after':0,'named_lock_released':True,'baseline_value':7,'other_connection_usable':True,'transaction_rollback_checked':name!='ordinary-error'}
        assert c['result']=='PASS',name
        if name=='ordinary-error':
            assert c['error_packets']==n['error_packets']
            assert c['ordinary_SQL_error_keeps_DB_usable']
        else:
            for record in (n,c):
                w=record['witness'];assert w['actor_id']==w['lock_owner'] and w['actor_id']>0 and w['uncommitted_write_hidden']
            assert c['fatal_DB']['code']=='unusable' and c['fatal_DB']['closed'] and c['fatal_DB']['new_SQL_admission_rejected']
            if name.startswith('go-') or name=='active-reset':
                for key in ('phase','result','kind','open_after','execute_error'):
                    assert c['consumer'][key]==n['consumer'][key],(name,key)
                if name=='active-reset':assert c['consumer']['transport_failed'] and n['consumer']['transport_failed']
    for name,c in r['cases'].items():
        assert c['result']=='PASS',name
        for key in ('target_log_removed','shared_lineage_retained_while_baseline_alive','sibling_usable_and_unchanged','baseline_reusable_with_prepared_QUERY','lineage_temporary_removed'):
            assert c[key],(name,key)
    assert r['cases']['host-deadline']['fatal_DB']['code']=='unusable'
    assert r['cases']['active-db-close']['explicit_Close_new_SQL_rejected']
    return {'native_connection_cleanup':'PASS','shared_observable_outcomes':'PASS',
            'disposition_difference':'native retains server and other connections; mariamem invalidates target DB, preserves independent siblings/baseline',
            'product_only':['host-deadline','active-db-close']}

def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--host');g.add_argument('--native-port',type=int)
    p.add_argument('--consumer',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--reference',type=Path)
    a=p.parse_args();r=exercise(a.consumer.resolve(),a.native_port,a.host)
    if a.reference:
        try:r['native_reference']=validate_reference(r,json.loads(a.reference.read_text()))
        except Exception as e:r.update(result='FAIL',reference_failure=repr(e))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    if r['result']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
