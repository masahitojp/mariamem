"""Bounded SQL DEFINER observations; no account/GRANT compatibility claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import pymysql
from pymysql.constants import CLIENT


def query(cursor, sql):
    try:
        cursor.execute(sql)
        sets=[]
        while True:
            sets.append(cursor.fetchall() if cursor.description else None)
            if not cursor.nextset(): break
        return {"outcome":"OK", "sets":sets}
    except pymysql.MySQLError as exc:
        return {"outcome":"ERROR", "errno":exc.args[0], "error":str(exc)}


def exercise(args, create=True):
    records=[]
    with pymysql.connect(**args,autocommit=True,client_flag=CLIENT.MULTI_RESULTS,read_timeout=30) as connection:
        with connection.cursor() as cursor:
            identity=query(cursor,"SELECT VERSION(), CURRENT_USER(), USER(), @@skip_grant_tables")
            for number,definer in enumerate([None,"CURRENT_USER","'root'@'localhost'","'absent_owner'@'example.invalid'"]):
                for security in ("DEFINER","INVOKER"):
                    for kind in ("PROCEDURE","FUNCTION"):
                        name=f"bounded_{number}_{security.lower()}_{kind.lower()}"
                        definition=("DEFINER="+definer+" ") if definer else ""
                        if kind=="PROCEDURE":
                            ddl=f"CREATE {definition}PROCEDURE test.{name}() SQL SECURITY {security} SELECT 7, CURRENT_USER(), USER()"
                            call=f"CALL test.{name}()"
                        else:
                            ddl=f"CREATE {definition}FUNCTION test.{name}() RETURNS VARCHAR(255) DETERMINISTIC SQL SECURITY {security} RETURN CONCAT('7|',COALESCE(CURRENT_USER(),'NULL'),'|',COALESCE(USER(),'NULL'))"
                            call=f"SELECT test.{name}()"
                        row={"case":name,"kind":kind,"definer_clause":definer,"security":security}
                        if create:
                            row['create']=query(cursor,ddl)
                        row['execute']=query(cursor,call)
                        row['metadata']=query(cursor,"SELECT DEFINER,SECURITY_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='test' AND ROUTINE_NAME='"+name+"'")
                        row['show_create']=query(cursor,f"SHOW CREATE {kind} test.{name}")
                        row['connection_health']=query(cursor,'SELECT 19')
                        assert row['connection_health']=={'outcome':'OK','sets':[((19,),)]},row
                        records.append(row)
    return {'identity':identity,'cases':records}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host')
    parser.add_argument('--native-port',type=int)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    result={'python':sys.version,'platform':platform.platform(),'scope':'minimum routine SQL and persistence, not account privilege enforcement'}
    if a.host:
        import mariamem
        result['host_sha256']=hashlib.sha256(Path(a.host).read_bytes()).hexdigest()
        resources=[]
        try:
            db=mariamem.start(host_binary=a.host);resources.append(db)
            result['guest_identity']=db._session.guest_identity
            result['fresh']=exercise(db.connection_info())
            db.wait_disconnected()
            baseline=db.snapshot();resources.append(baseline)
            for label in ('first_child','second_child'):
                child=baseline.fork();resources.append(child)
                result[label]=exercise(child.connection_info(),False)
                child.wait_disconnected()
                child.close()
            assert result['first_child']==result['second_child']
        finally:
            for resource in reversed(resources):resource.close()
    else:
        assert a.native_port
        result['native_control']='full system schema with grant tables; see identity skip_grant_tables value'
        result['fresh']=exercise(dict(host='127.0.0.1',port=a.native_port,user='root',database='test'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print('Recorded',len(result['fresh']['cases']),'bounded DEFINER cases',a.output)

if __name__=='__main__':main()
