"""Bounded official TypeORM and MikroORM MySQL dogfood; no product changes."""
import argparse
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import select
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
PROJECT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'python'),str(ROOT/'scripts')]
import mariamem
import pymysql
from git_identity import verify_go_binary

RUNTIME=('connect','count','find','create','bulk','nested','relation','update','upsert','delete_cascade','nullable','transaction_commit','transaction_rollback','unique_error','bigint','decimal','datetime','json','binary','raw_parameter','raw_zero_parameter','aggregate','group_by','schema_create','schema_noop','schema_update')



def env_for(info,off=False):
    env=dict(os.environ,DB_HOST=info['host'],DB_PORT=str(info['port']),DB_USER=info['user'],DB_PASSWORD=info['password'],DB_NAME='orm_matrix')
    env['DATABASE_URL']=f"mysql://{info['user']}:{info['password']}@{info['host']}:{info['port']}/orm_matrix"
    env.pop('PRISMA_PIPELINING',None)
    env.pop('PRISMA_PARAMETERIZED_COUNTS',None)
    env.pop('SHADOW_DATABASE_URL',None)
    env.pop('CI',None)
    if off:env['PRISMA_PIPELINING']='off'
    return env


def db(info):
    return pymysql.connect(host=info['host'],port=info['port'],user=info['user'],password=info['password'],autocommit=True)


def sql(info,text,params=None):
    with contextlib.closing(db(info)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(text,params)
            return cursor.fetchall()


def initialize(info,seed=False):
    sql(info,'CREATE DATABASE orm_matrix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    if seed:
        script=(PROJECT/'baseline.sql').read_text()
        for statement in script.split(';'):
            if statement.strip():sql_in_db(info,statement)
        sql_in_db(info,"INSERT INTO `User`(`id`,`email`,`name`) VALUES (1,'baseline@test','baseline')")
        sql_in_db(info,'INSERT INTO `Post`(`id`,`title`,`authorId`,`amount`,`big`,`at`,`meta`,`blob`) VALUES(1,%s,1,%s,%s,%s,%s,%s)',('baseline','12345678901234.123456',9007199254740993,datetime.datetime(2026,3,4,5,6,7,123000),json.dumps({'text':'日本語\u0000value','nested':[1,True,None]},ensure_ascii=False),bytes([0,1,0,127,128,255])))


def sql_in_db(info,text,params=None):
    with contextlib.closing(db(info)) as connection:
        with connection.cursor() as cursor:
            cursor.execute('USE orm_matrix')
            cursor.execute(text,params)
            return cursor.fetchall()


def last_json(text):
    for line in reversed(text.splitlines()):
        try:return json.loads(line)
        except json.JSONDecodeError:pass
    return {'result':'FAIL','error':text[-3000:]}


def run_node(orm,name,env,directory):
    p=subprocess.run(['node','cases.mjs',orm,name],cwd=PROJECT,env=env,text=True,capture_output=True,timeout=45)
    (directory/'node.txt').write_text(p.stdout+p.stderr)
    value=last_json(p.stdout)
    if p.returncode or value.get('result')!='PASS':raise RuntimeError(json.dumps(value,ensure_ascii=False))
    return value


def live_case(host,orm,directory):
    with mariamem.start(host_binary=host) as source:
        initialize(source.connection_info(),True)
        source.wait_disconnected(timeout=10)
        with source.snapshot() as baseline,baseline.live() as live:
            endpoint=live.connection_info();env=env_for(endpoint)
            with (directory/'node.txt').open('w') as log:
                app=subprocess.Popen(['node','cases.mjs',orm,'live'],cwd=PROJECT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True)
                def reply(command=None):
                    if command:app.stdin.write(json.dumps({'command':command})+'\n');app.stdin.flush()
                    deadline=time.monotonic()+45
                    while time.monotonic()<deadline:
                        if not select.select([app.stdout],[],[],max(0,deadline-time.monotonic()))[0]:break
                        text=app.stdout.readline();log.write(text);log.flush()
                        if not text:raise RuntimeError('Node exited')
                        try:value=json.loads(text)
                        except json.JSONDecodeError:continue
                        if value.get('result')=='FAIL':raise RuntimeError(json.dumps(value))
                        return value
                    raise TimeoutError('Node live response timeout')
                try:
                    ready=reply();assert ready['event']=='ready'
                    first=reply('read-mutate');assert first['pid']==ready['pid']
                    reply('disconnect')
                    live.reset(timeout=30,drain_timeout=5)
                    assert live.connection_info()==endpoint
                    second=reply('read-mutate');assert second['pid']==ready['pid']
                    reply('disconnect')
                    app.stdin.write('{"command":"quit"}\n');app.stdin.flush();app.stdin.close()
                    assert app.wait(timeout=10)==0
                    return {'same_node_pid':ready['pid'],'stable_endpoint':True,'restored_baseline':True}
                finally:
                    if app.poll() is None:
                        app.terminate()
                        try:app.wait(timeout=5)
                        except subprocess.TimeoutExpired:app.kill();app.wait(timeout=5)
                    app.stdout.close()
                    if not app.stdin.closed:app.stdin.close()


def main(host,output):
    output.mkdir(parents=True,exist_ok=True)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    info=verify_go_binary(ROOT,host,source)
    report={'scope':'ONE_OS_OFFICIAL_ORM_MYSQL_DOGFOOD','source_commit':source,'product_baseline_source_commit':subprocess.check_output(['git','rev-parse','origin/main'],cwd=ROOT,text=True).strip(),'host':{'system':platform.system(),'machine':platform.machine()},'node':subprocess.check_output(['node','--version'],text=True).strip(),'versions':{'typeorm':'1.1.2','mikro-orm':'7.2.7','mysql2':'3.24.6'},'binary_sha256':hashlib.sha256(host.read_bytes()).hexdigest(),'binary_build_info':info,'cells':[]}
    def cell(profile,name,operation):
        directory=output/(orm+'-'+name);directory.mkdir(exist_ok=True)
        row={'orm':orm,'name':name}
        try:row.update(result='PASS',observed=operation(directory))
        except Exception as error:row.update(result='FAIL',error=str(error))
        report['cells'].append(row)
        (output/'matrix.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(orm,name,row['result'],str(row.get('error',''))[:160],flush=True)
    for orm in ('typeorm','mikro'):
      for dialect in ('mysql','mariadb'):
        os.environ['DIALECT']=dialect
        profile=orm+'-'+dialect
        for name in RUNTIME:
            def operation(directory,n=name,o=orm):
                with mariamem.start(host_binary=host) as owner:
                    endpoint=owner.connection_info();initialize(endpoint,not n.startswith('schema_'))
                    return run_node(o,n,env_for(endpoint),directory)
            cell(profile,name,operation)
        cell(profile,'live-reset',lambda d,o=orm:live_case(host,o,d))
    report['summary']={o:{key:sum(r['orm']==o and r['result']==key for r in report['cells']) for key in ('PASS','FAIL')} for o in ('typeorm-mysql','typeorm-mariadb','mikro-mysql','mikro-mariadb')}
    (output/'matrix.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['summary']),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();main(args.host.resolve(),args.output.resolve())
