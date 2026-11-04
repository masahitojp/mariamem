"""Manual pinned Dub dogfood. Writes source-bound evidence; never installs or changes product code."""
import argparse,contextlib,hashlib,json,os,shutil,socket,subprocess,sys,time
from pathlib import Path

@contextlib.contextmanager
def planet_proxy(info,e):
    name='mariamem-dub-dogfood-ps'
    args=['docker','run','-d','--rm','--name',name,'--label','mariamem.task=dub-dogfood','-p','127.0.0.1:13900:3900','ghcr.io/mattrobenolt/ps-http-sim@sha256:fb624c2f615cd53910be07a5c6a62ddf54936a2e1c7322c8398fa2b5dd601c41','-listen-port=3900','-mysql-addr=host.docker.internal','-mysql-port='+str(info['port']),'-mysql-dbname=planetscale']
    if not info['password']:args.append('-mysql-no-pass')
    identifier=subprocess.check_output(args,text=True).strip()
    try:
        deadline=time.monotonic()+15
        while True:
            try:
                with socket.create_connection(('127.0.0.1',13900),timeout=1):break
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.25)
        yield f"http://{info['user']}:{info['password'] or 'unused'}@127.0.0.1:13900/planetscale"
    finally:
        with (e/'ps-http.txt').open('w') as log:subprocess.run(['docker','logs',name],stdout=log,stderr=subprocess.STDOUT)
        subprocess.run(['docker','rm','-f',name],check=True,stdout=subprocess.DEVNULL)

@contextlib.contextmanager
def qstash_local(path,e):
    config=json.loads(path.read_text())
    try:yield config
    finally:
        with (e/'qstash.txt').open('w') as log:subprocess.run(['docker','logs','mariamem-dub-dogfood-qstash'],stdout=log,stderr=subprocess.STDOUT)
        subprocess.run(['docker','rm','-f','mariamem-dub-dogfood-qstash'],check=True,stdout=subprocess.DEVNULL)

def main(w,e,redis_url,with_proxy,qstash_env,prewarm,server_mode):
    product=w/'temp/host-source';app=w/'temp/dub/apps/web';host=w/'temp/mariamem-host'
    e.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(product/'python'),str(product/'scripts')]
    import mariamem,pymysql
    from git_identity import verify_go_binary
    source='c27061f1a33eed2908fd90b0e2d816692e001339'
    stamp=verify_go_binary(product,host,source)
    report={'mariamem_source_commit':source,'dub_source_commit':'6b463b4bdd9ed2fd9aa416f67b5b77d317b1471e','binary_sha256':hashlib.sha256(host.read_bytes()).hexdigest(),'binary_build_info':stamp,'stages':[],'server_mode':server_mode}
    def save(): (e/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(name,args,env,timeout=120,cwd=app):
        with (e/(name+'.txt')).open('w') as log:
            try:
                p=subprocess.run(args,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
                row={'name':name,'exit_code':p.returncode,'result':'PASS' if p.returncode==0 else 'FAIL'}
            except subprocess.TimeoutExpired:row={'name':name,'result':'TIMEOUT'}
        report['stages'].append(row);save();print(name,row,flush=True);return row
    with contextlib.ExitStack() as stack:
        db=stack.enter_context(mariamem.start(host_binary=host,log_path=e/'host.log',query_timeout=30))
        info=db.connection_info()
        with contextlib.closing(pymysql.connect(**info,autocommit=True)) as c:
            with c.cursor() as cur:cur.execute('CREATE DATABASE planetscale CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        psurl=stack.enter_context(planet_proxy(info,e)) if with_proxy else None
        qscfg=stack.enter_context(qstash_local(qstash_env,e)) if qstash_env else None
        url=f"mysql://{info['user']}:{info['password']}@{info['host']}:{info['port']}/planetscale"
        import re
        clean_env=dict(os.environ)
        for key in re.findall(r'^([A-Z][A-Z0-9_]*)=',(app/'.env.example').read_text(),re.M):clean_env.pop(key,None)
        env=dict(clean_env,DATABASE_URL=url,COREPACK_HOME=str(w/'temp/corepack'),NEXT_TELEMETRY_DISABLED='1',NODE_ENV='development',NEXTAUTH_URL='http://localhost:8888',NEXTAUTH_SECRET='local-dogfood-only-secret-not-for-production',ENCRYPTION_KEY='0123456789abcdef0123456789abcdef',UPSTASH_REDIS_REST_URL=redis_url,UPSTASH_REDIS_REST_TOKEN='local-dogfood-only',QSTASH_URL='http://127.0.0.1:9',QSTASH_TOKEN='local-unconfigured',TINYBIRD_API_URL='http://127.0.0.1:9',TINYBIRD_API_KEY='local-unconfigured')
        for name in ('CI','VERCEL','VERCEL_ENV','PLANETSCALE_DATABASE_URL','PRISMA_PIPELINING'):env.pop(name,None)
        if psurl:env['PLANETSCALE_DATABASE_URL']=psurl
        if qscfg:env.update(qscfg,QSTASH_URL='http://127.0.0.1:18080',NEXT_PUBLIC_NGROK_URL='http://host.docker.internal:8888')
        env['PLAYWRIGHT_JSON_OUTPUT_FILE']=str(e/'upstream-api.json')
        cli=['corepack','pnpm','exec']
        run('schema-push',cli+['prisma','db','push','--schema=./prisma/schema','--skip-generate'],env)
        with contextlib.closing(pymysql.connect(**dict(info,database='planetscale'),autocommit=True)) as c:
            with c.cursor() as cur:cur.execute('SHOW TABLES');report['schema_tables']=[x[0] for x in cur.fetchall()]
        save()
        run('schema-push-idempotent',cli+['prisma','db','push','--schema=./prisma/schema','--skip-generate'],env)
        nodeenv=dict(env,NODE_OPTIONS='--conditions=react-server --import=./scripts/runtime/async-local-storage.cjs')
        run('upstream-seed',cli+['tsx','scripts/dev/seed.ts'],nodeenv)
        run('db-cases',cli+['tsx','.mariamem-dogfood.ts'],nodeenv)
        for line in reversed((e/'db-cases.txt').read_text().splitlines()):
            try:
                value=json.loads(line)
                if 'cells' in value:report['db_cases']=value;break
            except ValueError:pass
        save()
        if not report.get('db_cases'):return 1
        if psurl:
            (app/'.mariamem-edge-probe.ts').write_text("import assert from 'node:assert/strict'; import {prismaEdge} from './lib/prisma/edge'; async function main(){try{const r:any=await prismaEdge.$queryRawUnsafe('SELECT 1 AS n');assert.equal(Number(r[0].n),1);console.log('PASS_HTTP_PRISMA_EDGE');}finally{await prismaEdge.$disconnect();}} main().catch(e=>{console.error(e);process.exitCode=1;});\n")
            run('upstream-prisma-edge',cli+['tsx','.mariamem-edge-probe.ts'],nodeenv)

        # Probe the upstream local app and its existing API tests separately.
        s=socket.socket()
        try:s.bind(('127.0.0.1',8888))
        except OSError:
            report['upstream_http']={'result':'BLOCKED','reason':'port8888 already occupied; user process preserved'};save();return 1
        finally:s.close()
        with (e/'next-dev.txt').open('w') as log:
            serverenv=dict(env,NODE_OPTIONS='--require='+str(w/'worktree/benchmarks/spikes/dub-dogfood/local-fetch-only.cjs'))
            server=subprocess.Popen(cli+['next','dev',*(['--turbopack'] if server_mode=='turbopack' else []),'--hostname','127.0.0.1','--port','8888'],cwd=app,env=serverenv,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                until=time.monotonic()+90;ready=False
                while time.monotonic()<until and server.poll() is None:
                    try:
                        with socket.create_connection(('127.0.0.1',8888),timeout=.5):ready=True;break
                    except OSError:time.sleep(.25)
                report['upstream_http']={'listening':ready,'server_exit_code':server.poll()};save()
                if ready:
                    if prewarm:
                        import urllib.request,urllib.error
                        paths=['/customers','/customers/_dogfood_','/domains','/domains/_dogfood_.test','/domains/_dogfood_.test/primary','/domains/status','/folders','/folders/_dogfood_','/links','/links/bulk','/shopify/pixel','/shopify/integration/webhook','/tags','/tags/_dogfood_','/utm','/utm/_dogfood_','/workspaces/_dogfood_','/workspaces/_dogfood_/users']
                        warmed=[]
                        for path in paths:
                            try:
                                with urllib.request.urlopen('http://localhost:8888/api'+path,timeout=120) as response:response.read();status=response.status
                            except urllib.error.HTTPError as error:error.read();status=error.code
                            warmed.append({'path':path,'unauthenticated_get_status':status})
                        report['prewarm']=warmed;save()
                    run('upstream-api-tests',cli+['playwright','test','--project=api','--workers=1','--retries=0','--max-failures=0','--reporter=line,json'],env,timeout=600)
                else:report['upstream_http']['result']='BLOCKED_SERVER_START';save()
            finally:
                if server.poll() is None:
                    import signal
                    os.killpg(server.pid,signal.SIGTERM)
                    try:server.wait(timeout=15)
                    except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL);server.wait(timeout=5)
    save()
    print(json.dumps({'stages':report['stages'],'db_cases':report.get('db_cases',{}).get('summary')}),flush=True)
    return int(any(row['result']!='PASS' for row in report['stages']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--redis-url',default='http://127.0.0.1:9');p.add_argument('--with-proxy',action='store_true');p.add_argument('--qstash-env',type=Path);p.add_argument('--prewarm',action='store_true');p.add_argument('--server-mode',choices=['turbopack','webpack'],default='turbopack');a=p.parse_args();sys.exit(main(a.workspace.resolve(),a.output.resolve(),a.redis_url,a.with_proxy,a.qstash_env,a.prewarm,a.server_mode))
