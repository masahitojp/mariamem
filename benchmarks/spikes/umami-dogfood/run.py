"""Pinned Umami v2 MySQL migration, query and original Cypress API/UI dogfood."""
import argparse,contextlib,hashlib,json,os,re,signal,socket,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path

def main(w,e,compat,cohorts,native_port):
    product=w/'temp/host-source';app=w/'temp/umami';host=w/'temp/mariamem-host';e.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(product/'python'),str(product/'scripts')]
    import mariamem,pymysql
    from git_identity import verify_go_binary
    source='c27061f1a33eed2908fd90b0e2d816692e001339';stamp=verify_go_binary(product,host,source)
    report={'backend':'native-mariadb' if native_port else 'mariamem','binary_consumed':not bool(native_port),'snapshot_fork_used':not bool(native_port),'mariamem_source_commit':source,'umami_source_commit':'3eb2e890efb5b18bdfbeab46b9946f48e38da424','binary_sha256':hashlib.sha256(host.read_bytes()).hexdigest(),'binary_build_info':stamp,'stages':[],'cohorts':{}}
    def save():(e/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    env=dict(os.environ,COREPACK_HOME=str(w/'temp/corepack'),CYPRESS_CACHE_FOLDER=str(w/'temp/cypress-cache'),XDG_CACHE_HOME=str(w/'temp/xdg-cache'),NEXT_TELEMETRY_DISABLED='1',TZ='UTC',APP_SECRET='local-umami-dogfood-only-not-for-production',DATABASE_TYPE='mysql',NODE_ENV='development')
    for key in list(env):
        if key in ('ELECTRON_RUN_AS_NODE','NODE_OPTIONS','DATABASE_REPLICA_URL','REDIS_URL','CLICKHOUSE_URL','CLOUD_MODE','CLOUD_URL','VERCEL','CI','SKIP_DB_CHECK','SKIP_DB_MIGRATION') or key.startswith(('KAFKA_','CYPRESS_RECORD_')):env.pop(key,None)
    cli=['corepack','pnpm@9.15.9']
    def connection(db):
        info=db.connection_info();return dict(env,DATABASE_URL=f"mysql://{info['user']}:{info['password']}@{info['host']}:{info['port']}/umami")
    def run(name,args,localenv,timeout=180):
        with (e/(name+'.txt')).open('w') as log:
            try:p=subprocess.run(args,cwd=app,env=localenv,stdout=log,stderr=subprocess.STDOUT,timeout=timeout);row={'name':name,'result':'PASS' if p.returncode==0 else 'FAIL','exit_code':p.returncode}
            except subprocess.TimeoutExpired:row={'name':name,'result':'TIMEOUT'}
        report['stages'].append(row);save();print(name,row,flush=True);return row
    class NativeHandle:
        def connection_info(self):return {'host':'127.0.0.1','port':native_port,'user':'root','password':'','database':'mysql'}
    with contextlib.ExitStack() as outer:
        root=NativeHandle() if native_port else outer.enter_context(mariamem.start(host_binary=host,log_path=e/'host.log',query_timeout=30))
        info=root.connection_info()
        with contextlib.closing(pymysql.connect(**info,autocommit=True)) as c:
            with c.cursor() as cur:cur.execute('CREATE DATABASE umami CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            if compat:
                with c.cursor() as cur:
                    cur.execute('USE umami');cur.execute((w/'worktree/benchmarks/spikes/umami-dogfood/diagnostic-bin-to-uuid.sql').read_text())
                    cur.execute("SELECT BIN_TO_UUID(UNHEX('6ccd780cbaba102695645b8c656024db'))");assert cur.fetchone()[0]=='6ccd780c-baba-1026-9564-5b8c656024db'
                report['diagnostic_compatibility_function']=True;save()
        localenv=connection(root)
        if run('migration-deploy',cli+['exec','prisma','migrate','deploy'],localenv)['result']!='PASS':return 1
        run('upstream-check-db-repeat',cli+['run','check-db'],localenv)
        with contextlib.closing(pymysql.connect(**dict(info,database='umami'),autocommit=True)) as c:
            with c.cursor() as cur:
                cur.execute('SELECT migration_name,finished_at IS NOT NULL FROM _prisma_migrations ORDER BY migration_name');report['migrations']=[list(x) for x in cur.fetchall()]
                cur.execute('SHOW TABLES');report['tables']=[x[0] for x in cur.fetchall()]
        save()
        if not native_port:root.wait_disconnected(timeout=10)
        with (contextlib.nullcontext(None) if native_port else root.snapshot(max_forks=3)) as baseline:
            if "queries" in cohorts:
                with (contextlib.nullcontext(root) if native_port else baseline.fork()) as db:
                    run('application-query-cases',['node','.mariamem-db.cjs'],connection(db))
                    for line in reversed((e/'application-query-cases.txt').read_text().splitlines()):
                        try:
                            value=json.loads(line)
                            if 'cells' in value:report['query_cases']=value;break
                        except ValueError:pass
                    save()
            for mode,spec in [('api','cypress/e2e/api-*.cy.ts'),('ui','cypress/e2e/login.cy.ts,cypress/e2e/user.cy.ts,cypress/e2e/website.cy.ts')]:
                if mode not in cohorts:continue
                with (contextlib.nullcontext(root) if native_port else baseline.fork()) as db:
                    localenv=connection(db)
                    probe=socket.socket()
                    try:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
                    finally:probe.close()
                    base_url='http://localhost:'+str(port);localenv['UMAMI_DOGFOOD_BASE_URL']=base_url
                    with (e/(mode+'-next.txt')).open('w') as log:
                        server=subprocess.Popen(cli+['exec','next','dev','--turbopack','--hostname','127.0.0.1','--port',str(port)],cwd=app,env=localenv,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                        try:
                            deadline=time.monotonic()+90
                            while True:
                                if server.poll() is not None:raise RuntimeError('Next dev-turbo failed; inspect '+mode+'-next.txt')
                                try:
                                    with socket.create_connection(('127.0.0.1',port),timeout=.5):break
                                except OSError:
                                    if time.monotonic()>deadline:raise TimeoutError('Next startup')
                                    time.sleep(.25)
                            # Unauthenticated GET compiles routes only; 401/405 are expected here.
                            stub='11111111-1111-4111-8111-111111111111'
                            paths=['/api/auth/login','/api/auth/verify','/api/teams','/api/teams/'+stub,'/api/teams/'+stub+'/users','/api/users','/api/users/'+stub,'/api/websites','/api/websites/'+stub,'/api/me','/api/me/websites','/api/me/teams','/api/users/'+stub+'/websites','/api/users/'+stub+'/teams','/api/heartbeat']
                            if mode=='ui':paths+=['/login','/dashboard','/settings/websites','/settings/websites/'+stub,'/settings/users','/settings/users/'+stub,'/settings/profile']
                            prep=[]
                            for path in paths:
                                try:
                                    with urllib.request.urlopen(base_url+path,timeout=120) as r:r.read();status=r.status
                                except urllib.error.HTTPError as error:error.read();status=error.code
                                prep.append({'path':path,'status':status})
                            report['cohorts'][mode]={'prepared_routes':prep};save()
                            run(mode+'-cypress',['node','.mariamem-cypress.cjs',spec,str(e/(mode+'-cypress.json'))],localenv,timeout=900)
                        finally:
                            if server.poll() is None:
                                os.killpg(server.pid,signal.SIGTERM)
                                try:server.wait(timeout=15)
                                except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL);server.wait(timeout=5)
                    save()
    save();return int(any(s['result']!='PASS' for s in report['stages']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--diagnostic-compat',action='store_true');p.add_argument('--cohorts',default='queries,api,ui');p.add_argument('--native-port',type=int);a=p.parse_args();sys.exit(main(a.workspace.resolve(),a.output.resolve(),a.diagnostic_compat,set(a.cohorts.split(',')),a.native_port))
