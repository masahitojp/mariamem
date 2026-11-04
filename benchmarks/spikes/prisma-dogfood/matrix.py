"""Independent Prisma Client and CLI cells, including actual shadow DB commands."""
import argparse
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import pty
import select
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
PROJECT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'python'),str(ROOT/'scripts')]
import mariamem
import pymysql
from git_identity import verify_go_binary

RUNTIME=('connect','find_unique','find_many_unfiltered','count_unfiltered','count_filtered','create','nested_create','create_many','update','delete_cascade','upsert','relation','nullable','transaction_commit','transaction_rollback','transaction_array','aggregate','group_by','raw_parameter','raw_zero_parameter','execute_raw','unique_error','decimal','bigint','datetime','json','binary')
CLI=('validate','generate','db_execute','db_push','db_pull','migrate_deploy','migrate_status','migrate_reset','migrate_dev_auto_shadow','migrate_dev_explicit_shadow','migrate_dev_create_only','diff_schema','diff_migrations_shadow','resolve_applied','resolve_rolled_back')


def env_for(info,off=False):
    env=dict(os.environ,DB_HOST=info['host'],DB_PORT=str(info['port']),DB_USER=info['user'],DB_PASSWORD=info['password'],DB_NAME='prisma_matrix')
    env['DATABASE_URL']=f"mysql://{info['user']}:{info['password']}@{info['host']}:{info['port']}/prisma_matrix"
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
    sql(info,'CREATE DATABASE prisma_matrix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    if seed:
        script=(PROJECT/'prisma/migrations/20261104000000_init/migration.sql').read_text()
        for statement in script.split(';'):
            if statement.strip():sql_in_db(info,statement)
        sql_in_db(info,"INSERT INTO User(id,email,name) VALUES (1,'baseline@test','baseline')")
        sql_in_db(info,'INSERT INTO Post(id,title,authorId,amount,big,at,meta,blob) VALUES(1,%s,1,%s,%s,%s,%s,%s)',('baseline','12345678901234.123456',9007199254740993,datetime.datetime(2026,3,4,5,6,7,123000),json.dumps({'text':'日本語\u0000value','nested':[1,True,None]},ensure_ascii=False),bytes([0,1,0,127,128,255])))


def sql_in_db(info,text,params=None):
    with contextlib.closing(db(info)) as connection:
        with connection.cursor() as cursor:
            cursor.execute('USE prisma_matrix')
            cursor.execute(text,params)
            return cursor.fetchall()


def last_json(text):
    for line in reversed(text.splitlines()):
        try:return json.loads(line)
        except json.JSONDecodeError:pass
    return {'result':'FAIL','error':text[-3000:]}


def run_node(name,env,directory):
    p=subprocess.run(['node','--import','tsx','matrix.ts',name],cwd=PROJECT,env=env,text=True,capture_output=True,timeout=45)
    (directory/'node.txt').write_text(p.stdout+p.stderr)
    value=last_json(p.stdout)
    if p.returncode or value.get('result')!='PASS':raise RuntimeError(json.dumps(value,ensure_ascii=False))
    return value


def live_case(host,off,directory):
    with mariamem.start(host_binary=host) as source:
        initialize(source.connection_info(),True)
        source.wait_disconnected(timeout=10)
        with source.snapshot() as baseline,baseline.live() as live:
            endpoint=live.connection_info();env=env_for(endpoint,off)
            with (directory/'node.txt').open('w') as log:
                app=subprocess.Popen(['node','--import','tsx','matrix.ts','live'],cwd=PROJECT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True)
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


def tty_command(args,cwd,env):
    master,slave=pty.openpty();text=b'';answered=0
    process=subprocess.Popen(args,cwd=cwd,env=dict(env,TERM='xterm',NO_COLOR='1'),stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
    os.close(slave);deadline=time.monotonic()+90
    try:
        while True:
            if time.monotonic()>deadline:raise TimeoutError('CLI PTY timeout')
            if select.select([master],[],[],.2)[0]:
                try:chunk=os.read(master,65536)
                except OSError:break
                if not chunk:break
                text+=chunk
                # Only this isolated throwaway database is ever confirmed.
                prompts=text.count(b'(y/N)')+text.count(b'(Y/n)')
                if prompts>answered:os.write(master,b'y\n');answered=prompts
            elif process.poll() is not None:break
        return process.wait(timeout=5),text.decode(errors='replace')
    finally:
        os.close(master)
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


def cli_case(name,host,directory):
    case=PROJECT/'.matrix'/name
    case.mkdir(parents=True,exist_ok=True)
    shutil.copytree(PROJECT/'prisma',case/'prisma',dirs_exist_ok=True)
    config=case/'prisma.config.ts'
    config.write_text("import {defineConfig,env} from 'prisma/config'; export default defineConfig({schema:'prisma/schema.prisma',migrations:{path:'prisma/migrations'},datasource:{url:env('DATABASE_URL'),...(process.env.SHADOW_DATABASE_URL?{shadowDatabaseUrl:process.env.SHADOW_DATABASE_URL}:{})}});\n")
    steps=[]
    with mariamem.start(host_binary=host) as source:
        info=source.connection_info();initialize(info,seed=name in ('db_pull','resolve_applied'))
        env=env_for(info)
        if name in ('migrate_dev_explicit_shadow','migrate_dev_create_only','diff_migrations_shadow'):
            sql(info,'CREATE DATABASE prisma_shadow')
            env['SHADOW_DATABASE_URL']=env['DATABASE_URL'].replace('/prisma_matrix','/prisma_shadow')
        def command(arguments,label,expected=(0,),tty=False,input=None):
            args=[str(PROJECT/'node_modules/.bin/prisma'),*arguments,'--config',str(config)]
            if tty:code,text=tty_command(args,case,env)
            else:
                p=subprocess.run(args,cwd=case,env=env,input=input,text=True,capture_output=True,timeout=90)
                code,text=p.returncode,p.stdout+p.stderr
            (directory/(label+'.txt')).write_text(text)
            steps.append({'command':arguments,'exit_code':code,'expected':list(expected),'pty':tty})
            if code not in expected:raise RuntimeError(label+': '+text[-6000:])
            return text
        if name in ('migrate_status','migrate_reset','diff_schema','diff_migrations_shadow','resolve_rolled_back'):
            command(['migrate','deploy'],'setup-deploy')
        if name=='validate':command(['validate'],'validate')
        elif name=='generate':command(['generate'],'generate');assert (case/'generated/client.ts').exists()
        elif name=='db_execute':
            command(['db','execute','--stdin'],'execute',input='CREATE TABLE Probe(n INT); INSERT INTO Probe VALUES(7);')
            assert sql_in_db(info,'SELECT n FROM Probe')==((7,),)
        elif name=='db_push':command(['db','push'],'push');assert sql_in_db(info,'SELECT COUNT(*) FROM User')==((0,),)
        elif name=='db_pull':text=command(['db','pull','--print'],'pull');assert 'model User' in text and 'model Post' in text
        elif name=='migrate_deploy':command(['migrate','deploy'],'deploy');assert sql_in_db(info,'SELECT COUNT(*) FROM _prisma_migrations')==((1,),)
        elif name=='migrate_status':text=command(['migrate','status'],'status');assert 'up to date' in text.lower()
        elif name=='migrate_reset':
            sql_in_db(info,"INSERT INTO User(email) VALUES ('removed@test')")
            command(['migrate','reset','--force'],'reset')
            assert sql_in_db(info,'SELECT COUNT(*) FROM User')==((0,),)
        elif name in ('migrate_dev_auto_shadow','migrate_dev_explicit_shadow'):
            command(['migrate','dev','--name','dogfood'],'dev',tty=True)
            assert sql_in_db(info,'SELECT COUNT(*) FROM _prisma_migrations')[0][0]>=1
        elif name=='migrate_dev_create_only':
            schema=case/'prisma/schema.prisma';schema.write_text(schema.read_text().replace('  name String?', '  note String?\n  name String?'))
            command(['migrate','dev','--create-only','--name','add_note'],'create-only',tty=True)
            new=[p for p in (case/'prisma/migrations').glob('*/migration.sql') if p.parent.name!='20261104000000_init']
            assert new and any('note' in p.read_text() for p in new)
            assert not sql_in_db(info,"SHOW COLUMNS FROM User LIKE 'note'")
        elif name=='diff_schema':
            schema=case/'prisma/schema.prisma';schema.write_text(schema.read_text().replace('  name String?', '  note String?\n  name String?'))
            text=command(['migrate','diff','--from-config-datasource','--to-schema',str(schema),'--script','--exit-code'],'diff-schema',expected=(2,))
            assert 'note' in text
        elif name=='diff_migrations_shadow':command(['migrate','diff','--from-migrations',str(case/'prisma/migrations'),'--to-config-datasource','--exit-code'],'diff-migrations')
        elif name=='resolve_applied':
            command(['migrate','resolve','--applied','20261104000000_init'],'resolve-applied')
            assert sql_in_db(info,'SELECT COUNT(*) FROM _prisma_migrations WHERE finished_at IS NOT NULL')==((1,),)
        elif name=='resolve_rolled_back':
            bad=case/'prisma/migrations/20261104000001_bad';bad.mkdir();(bad/'migration.sql').write_text('INVALID DOGFOOD SQL;')
            text=command(['migrate','deploy'],'intentional-failed-migration',expected=(1,));assert 'P3018' in text
            command(['migrate','resolve','--rolled-back','20261104000001_bad'],'resolve-rolled-back')
            assert sql_in_db(info,"SELECT COUNT(*) FROM _prisma_migrations WHERE migration_name='20261104000001_bad' AND rolled_back_at IS NOT NULL")==((1,),)
    return {'steps':steps}


def main(host,output):
    output.mkdir(parents=True,exist_ok=True)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    info=verify_go_binary(ROOT,host,source)
    report={'scope':'ONE_OS_PRISMA_7_10_1_REPRESENTATIVE_CLIENT_AND_COMPLETE_LISTED_CLI_MATRIX','source_commit':source,'product_baseline_source_commit':'bc00b8e66e5fd57bc9b2127001faf8e05952b417','host':{'system':platform.system(),'machine':platform.machine()},'node':subprocess.check_output(['node','--version'],text=True).strip(),'versions':{'prisma':'7.10.1','adapter':'7.10.1','mariadb':'3.5.4'},'binary_sha256':hashlib.sha256(host.read_bytes()).hexdigest(),'binary_build_info':info,'cells':[]}
    def cell(name,kind,operation):
        directory=output/name;directory.mkdir(exist_ok=True)
        row={'name':name,'kind':kind}
        try:row.update(result='PASS',observed=operation(directory))
        except Exception as error:row.update(result='FAIL',error=str(error))
        report['cells'].append(row)
        (output/'matrix.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(name,row['result'],str(row.get('error',''))[:130],flush=True)
    for name in CLI:cell('cli-'+name,'CLI',lambda d,n=name:cli_case(n,host,d))
    for off in (False,True):
        mode='off' if off else 'default'
        for name in RUNTIME:
            def operation(directory,n=name,o=off):
                with mariamem.start(host_binary=host) as owner:
                    endpoint=owner.connection_info();initialize(endpoint,True)
                    return run_node(n,env_for(endpoint,o),directory)
            cell(mode+'-'+name,'Client',operation)
        cell(mode+'-live-reset','Live',lambda d,o=off:live_case(host,o,d))
    report['summary']={key:sum(r['result']==key for r in report['cells']) for key in ('PASS','FAIL')}
    (output/'matrix.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['summary']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();main(args.host.resolve(),args.output.resolve())
