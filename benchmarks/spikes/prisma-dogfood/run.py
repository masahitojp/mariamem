"""One-host Prisma consumer spike. No Node SDK, automatic CI or performance claim."""
import argparse
import contextlib
import hashlib
import json
import os
import platform
from pathlib import Path
import select
import subprocess
import sys
import urllib.parse

ROOT=Path(__file__).resolve().parents[3]
PROJECT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'python'))
import mariamem
import pymysql
sys.path.insert(0,str(ROOT/'scripts'))
from git_identity import verify_go_binary


def run(host, output):
    output.mkdir(parents=True,exist_ok=True)
    report={'result':'FAIL','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'host':{'system':platform.system(),'machine':platform.machine()},'node':subprocess.check_output(['node','--version'],text=True).strip(),'prisma':'7.10.1','adapter':'7.10.1','driver':'mariadb 3.5.4','stages':[]}
    def command(args, env, name):
        result=subprocess.run(args,cwd=PROJECT,env=env,text=True,capture_output=True,timeout=120)
        (output/(name+'.txt')).write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(name+' failed: '+(result.stdout+result.stderr)[-6000:])
        return result.stdout
    def environment(info):
        env=dict(os.environ,DB_HOST=info['host'],DB_PORT=str(info['port']),DB_USER=info['user'],DB_PASSWORD=info['password'],DB_NAME='prisma_dogfood')
        env['DATABASE_URL']='mysql://'+urllib.parse.quote(info['user'],safe='')+':'+urllib.parse.quote(info['password'],safe='')+'@'+info['host']+':'+str(info['port'])+'/prisma_dogfood'
        return env
    try:
        report['binary_build_info']=verify_go_binary(ROOT,host,report['source_commit'])
        report['binary_sha256']=hashlib.sha256(host.read_bytes()).hexdigest()
        with mariamem.start(host_binary=host) as source:
            info=source.connection_info()
            with contextlib.closing(pymysql.connect(host=info['host'],port=info['port'],user=info['user'],password=info['password'],autocommit=True)) as connection:
                with connection.cursor() as cursor:cursor.execute('CREATE DATABASE prisma_dogfood CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            env=environment(info)
            command(['node_modules/.bin/prisma','migrate','deploy'],env,'migrate')
            report['stages'].append({'migration':'PASS'})
            seed=json.loads(command(['node','--import','tsx','app.ts','seed'],env,'seed').strip().splitlines()[-1])
            assert seed['result']=='PASS',seed
            report['stages'].append(seed)
            source.wait_disconnected(timeout=15)
            with source.snapshot() as baseline, baseline.live() as live:
                endpoint=live.connection_info()
                with (output/'node-stderr.txt').open('w') as errorlog:
                    app=subprocess.Popen(['node','--import','tsx','app.ts','serve'],cwd=PROJECT,env=environment(endpoint),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errorlog,text=True)
                    def reply(request=None):
                        if request:
                            app.stdin.write(json.dumps({'command':request})+'\n');app.stdin.flush()
                        if not select.select([app.stdout],[],[],60)[0]:raise TimeoutError('Node response timeout')
                        text=app.stdout.readline()
                        if not text:raise RuntimeError('Node exited: '+(output/'node-stderr.txt').read_text()[-4000:])
                        value=json.loads(text)
                        if value.get('result')=='FAIL':raise RuntimeError(json.dumps(value))
                        return value
                    try:
                        ready=reply();assert ready['event']=='ready',ready
                        for index in range(2):
                            case=reply('case');assert case['result']=='PASS' and case['pid']==ready['pid'],case
                            report['stages'].append(case)
                            report['stages'].append(reply('disconnect'))
                            if index==0:
                                live.reset(timeout=60,drain_timeout=10)
                                assert live.connection_info()==endpoint
                                report['stages'].append({'reset':'PASS','stable_endpoint':True,'same_node_pid':ready['pid']})
                        app.stdin.write(json.dumps({'command':'quit'})+'\n');app.stdin.flush();app.stdin.close()
                        assert app.wait(timeout=10)==0
                    finally:
                        if app.poll() is None:
                            app.terminate()
                            try:app.wait(timeout=5)
                            except subprocess.TimeoutExpired:app.kill();app.wait(timeout=5)
                        app.stdout.close()
                        if not app.stdin.closed:app.stdin.close()
        report['result']='PASS'
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.host.resolve(),args.output.resolve())
