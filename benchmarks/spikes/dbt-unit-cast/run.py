#!/usr/bin/env python3
"""Experimental one-case dbt fixture-cast comparison; exclusive endpoints only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'python')]
from git_identity import verify_go_binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route', choices=['native', 'guest'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--host-binary', type=Path)
    args = parser.parse_args()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==args.source_commit
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)
    args.output.mkdir(parents=True,exist_ok=False)
    result = {'result':'FAIL','source_commit':args.source_commit,'route':args.route,'steps':[]}
    db = None
    conn = None
    try:
        import mysql.connector
        if args.route == 'guest':
            import mariamem
            result['host_buildinfo'] = verify_go_binary(ROOT,args.host_binary,args.source_commit)
            result['host_sha256'] = hashlib.sha256(args.host_binary.read_bytes()).hexdigest()
            db = mariamem.Database(host_binary=args.host_binary,query_timeout=30)
            endpoint=db.connection_info(); root=db._session.root
        else:
            endpoint=dict(host='127.0.0.1',port=33321,user='root',password='')
        conn=mysql.connector.connect(**endpoint)
        cur=conn.cursor();cur.execute('select version()');result['version']=cur.fetchone()[0]
        assert result['version'].startswith('12.3.3')
        cur.execute('DROP DATABASE IF EXISTS unit_probe');conn.commit()
        project=args.output/'project';shutil.copytree(Path(__file__).parent/'project',project)
        profile={'unit_probe':{'target':'dev','outputs':{'dev':{'type':'mariadb','server':endpoint['host'],
                 'port':endpoint['port'],'username':endpoint['user'],'password':endpoint['password'],
                 'schema':'unit_probe','threads':1}}}}
        (project/'profiles.yml').write_text(json.dumps(profile))
        macro=project/'macros/integer_cast.sql'; override=macro.read_text();macro.unlink()
        def run(label, arguments, expected_exit, expected_status):
            env=dict(os.environ,DBT_SEND_ANONYMOUS_USAGE_STATS='false',DBT_USE_COLORS='false',DO_NOT_TRACK='1')
            with (args.output/(label+'.txt')).open('wb') as log:
                proc=subprocess.run([str(Path(sys.executable).with_name('dbt')),*arguments,'--project-dir',str(project),
                                     '--profiles-dir',str(project)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            artifact=json.loads((project/'target/run_results.json').read_text())
            statuses=[r['status'] for r in artifact['results']]
            (args.output/(label+'-results.json')).write_text(json.dumps(artifact,indent=2)+'\n')
            step={'label':label,'exit_code':proc.returncode,'statuses':statuses};result['steps'].append(step)
            assert proc.returncode==expected_exit and statuses==[expected_status],step
            sql=project/'target/compiled/unit_probe/models/unit.yml/models/doubles_amount.sql'
            if sql.exists():shutil.copyfile(sql,args.output/(label+'.sql'))
            return artifact
        run('upstream',['run','--select','orders'],0,'success')
        baseline=run('without-override',['test','--select','test_type:unit'],1,'error')
        assert '1064 (42000)' in baseline['results'][0]['message']
        macro.write_text(override)
        run('with-override',['test','--select','test_type:unit'],0,'pass')
        unit=project/'models/unit.yml';unit.write_text(unit.read_text().replace('doubled: 14','doubled: 15'))
        run('wrong-expectation',['test','--select','test_type:unit'],1,'fail')
        cur.execute('SELECT 1');assert cur.fetchone()==(1,)
        result['subsequent_select']='PASS'
        cur.execute('DROP DATABASE unit_probe')
        cur.execute("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='unit_probe'")
        result['schema_count_after']=cur.fetchone()[0];assert result['schema_count_after']==0
        cur.close();result['result']='PASS'
    except BaseException as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        try:
            if conn is not None:conn.close()
            if db is not None:
                try:
                    db.wait_disconnected(timeout=5)
                    result['connections_after']=db.status()['active_connections']
                finally:db.close()
                result['host_reaped']=db._session._process.poll() is not None
                result['session_directory_removed']=not root.exists()
                assert result['host_reaped'] and result['session_directory_removed']
        finally:
            (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
