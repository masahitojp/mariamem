"""Bounded authored Alembic -> prepare -> Snapshot -> two application tests."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(mode, code, counts, events, contacts):
    def named(name): return [e for e in events if e['event']==name]
    cleanup = named('source_cleanup')
    common = (len(named('source_start'))==len(named('prepare_start'))==len(cleanup)==1
              and all(cleanup[0][key] for key in ['closed','host_reaped','directory_removed'])
              and len(named('preparation_original_profile_refused'))==1 and contacts==0
              and len(named('preparation_engines_disposed'))==1)
    if mode=='success':
        passed = named('test_pass')
        return (common and code==0 and counts=={'tests':2,'errors':0,'failures':0,'skipped':0}
                and len(named('prepared_state'))==1
                and len(named('snapshot_attempt'))==len(named('snapshot_success'))==1
                and len(passed)==2 and len({e['child'] for e in passed})==2
                and {e['name'] for e in passed}=={'commit','independent_initial_state'}
                and len(named('preparation_disconnected'))==1
                and named('preparation_disconnected')[0]['active_connections']==0)
    error = named('prepare_error')
    expected_stage = {'revision_failure':'migration','seed_failure':'seed'}[mode]
    return (common and code==1 and counts=={'tests':2,'errors':2,'failures':0,'skipped':0}
            and len(error)==1 and error[0]['stage']==expected_stage and error[0].get('oracle')==mode
            and error[0]['exception']=='ProgrammingError'
            and error[0]['original_exception']=='ProgrammingError' and error[0]['errno']==1146
            and not any(named(n) for n in ['prepared_state','snapshot_attempt','snapshot_success','test_pass']))


class Sentinel:
    def __init__(self):
        self.socket=socket.socket();self.socket.bind(('127.0.0.1',0));self.socket.listen()
        self.socket.settimeout(.1);self.port=self.socket.getsockname()[1]
        self.contacts=0;self.stop=threading.Event()
        self.worker=threading.Thread(target=self._accept,daemon=True);self.worker.start()
    def _accept(self):
        while not self.stop.is_set():
            try: connection,_=self.socket.accept()
            except socket.timeout:continue
            except OSError:return
            self.contacts+=1;connection.close()
    def close(self):
        self.stop.set();self.worker.join(timeout=1);self.socket.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--source-commit',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=a.runtime_root.resolve();out=a.output.resolve()
    code=Path(__file__).resolve().parent
    temp=out/'temp';evidence=out/'evidence';temp.mkdir(parents=True,exist_ok=True);evidence.mkdir(exist_ok=True)
    for name in ['os-tmp','go-tmp']:(temp/name).mkdir(exist_ok=True)
    sys.path.insert(0,str(root/'scripts'))
    from git_identity import require_commit,verify_go_binary
    identity=require_commit(root,a.source_commit)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==identity.source_commit
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
    env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',
             GOCACHE=str(temp/'gocache'),GOMODCACHE=str(temp/'modcache'),GOPATH=str(temp/'gopath'),
             GOTMPDIR=str(temp/'go-tmp'),TMPDIR=str(temp/'os-tmp'),
             PYTHONPATH=os.pathsep.join([str(root/'python'),str(code)]),
             PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTEST_ADDOPTS='')
    host=temp/'mariamem-host'
    with (evidence/'host-build.txt').open('w') as log:
        subprocess.run(['go','build','-p','1','-trimpath','-o',str(host),'./cmd/mariamem-host'],
                       cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    original=dict(os.environ)
    try:
        os.environ.update(env);buildinfo=verify_go_binary(root,host,identity.source_commit)
    finally:
        os.environ.clear();os.environ.update(original)
    installed={name:importlib.metadata.version(name) for name in ['Alembic','SQLAlchemy','PyMySQL','pytest']}
    assert installed=={'Alembic':'1.18.4','SQLAlchemy':'2.0.54','PyMySQL':'1.2.3','pytest':'9.0.2'}
    (evidence/'alembic-version.txt').write_text(subprocess.check_output([sys.executable,'-m','alembic','--version'],text=True))
    receipt={'source_commit':identity.source_commit,'fixture_origin':'repository-authored example; not an existing production application',
             'python':sys.version,'platform':platform.platform(),'packages':installed,
             'guest_sha256':json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256'],
             'host_sha256':digest(host),'host_buildinfo':buildinfo,
             'fixture_files':{str(f.relative_to(code)):digest(f) for f in sorted(code.rglob('*')) if f.is_file() and '__pycache__' not in f.parts},
             'sdk_files':{str(f.relative_to(root)):digest(f) for f in sorted((root/'python/mariamem').glob('*.py'))},'runs':{}}
    (evidence/'results.json').write_text(json.dumps(receipt,indent=2)+'\n')
    sentinel=Sentinel()
    try:
        for mode in ['success','revision_failure','seed_failure']:
            mode_dir=evidence/mode;mode_dir.mkdir(exist_ok=True)
            events_path=mode_dir/'events.jsonl';events_path.write_text('')
            mode_env=dict(env,MIGRATION_HOST=str(host),MIGRATION_MODE=mode,
                          MIGRATION_EVENTS=str(events_path),MIGRATION_ORIGINAL_PORT=str(sentinel.port))
            argv=[sys.executable,'-m','pytest','-p','mariamem.pytest_plugin',
                  '--mariamem-route',f'app=127.0.0.1:{sentinel.port}/app',
                  str(code/'workflow.py'),'-q','--tb=short','--junitxml',str(mode_dir/'pytest.xml')]
            before=sentinel.contacts
            with (mode_dir/'pytest.txt').open('w') as log:
                process=subprocess.Popen(argv,cwd=root,env=mode_env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:exit_code=process.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL);process.wait()
                    raise RuntimeError('pytest scenario timed out; not a PASS')
            events=[json.loads(line) for line in events_path.read_text().splitlines()]
            suites=ET.parse(mode_dir/'pytest.xml').getroot().findall('.//testsuite')
            counts={key:sum(int(s.get(key,0)) for s in suites) for key in ['tests','errors','failures','skipped']}
            contacts=sentinel.contacts-before
            accepted=assess(mode,exit_code,counts,events,contacts)
            receipt['runs'][mode]={'exit':exit_code,'counts':counts,'original_endpoint_contacts':contacts,'accepted':accepted}
            print(mode,receipt['runs'][mode],flush=True)
    finally:
        sentinel.close()
        receipt['original_endpoint_contacts']=sentinel.contacts
        receipt['complete']=len(receipt['runs'])==3 and all(r['accepted'] for r in receipt['runs'].values()) and sentinel.contacts==0
        receipt['evidence']={str(f.relative_to(evidence)):digest(f) for f in sorted(evidence.rglob('*')) if f.is_file() and f.name!='results.json'}
        (evidence/'results.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['complete'] else 1


if __name__=='__main__':sys.exit(main())
