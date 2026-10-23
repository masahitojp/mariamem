"""Fixed-source real-guest experiment runner; not a product qualification gate."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

BASE = 'dfa6b21c4b4fb2c6e5e7e5db0d21eeef52394776'
GUEST = '8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40'
MUTATIONS = {'no_pool_check':'R2', 'fallback':'R5', 'ignore_retired':'R5', 'global_target':'R4'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--host',type=Path)
    p.add_argument('--go-consumer',type=Path)
    p.add_argument('--allow-connector-import-skip',action='store_true')
    a=p.parse_args(); root=a.runtime_root.resolve(); out=a.output.resolve()
    code=Path(__file__).resolve().parent
    temp=out/'temp'; evidence=out/'evidence'
    temp.mkdir(parents=True,exist_ok=True);evidence.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(root/'scripts'))
    from git_identity import require_commit, verify_go_binary
    identity=require_commit(root,BASE)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==BASE
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
    assert json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256']==GUEST
    env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOCACHE=str(temp/'gocache'),GOMODCACHE=str(temp/'modcache'),GOPATH=str(temp/'gopath'),PYTHONPATH=str(root/'python'),PYTHONDONTWRITEBYTECODE='1')
    host=a.host.resolve() if a.host else temp/'mariamem-host'
    go=a.go_consumer.resolve() if a.go_consumer else temp/'go-consumer'
    def command(argv,log,cwd=root):
        r=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (evidence/log).write_text(r.stdout)
        return r
    if not a.host:
        r=command(['go','build','-p','1','-trimpath','-o',host,'./cmd/mariamem-host'],'host-build.txt')
        if r.returncode:raise RuntimeError('host build failed; see log')
    # Verify source before consuming the binary; no source inferred from filename.
    original=dict(os.environ)
    try:
        os.environ.update(env)
        buildinfo=verify_go_binary(root,host,BASE)
    finally:
        os.environ.clear();os.environ.update(original)
    if not a.go_consumer:
        r=command(['go','build','-p','1','-trimpath','-o',go,code/'go_consumer.go'],'go-consumer-build.txt')
        if r.returncode:raise RuntimeError('Go consumer build failed; see log')
    installed={}
    for name,expected in [('PyMySQL','1.2.3'),('SQLAlchemy','2.0.54'),('mysql-connector-python','26.7.0')]:
        assert importlib.metadata.version(name)==expected
        dist=importlib.metadata.distribution(name)
        files={str(f):digest(Path(dist.locate_file(f))) for f in dist.files or [] if str(f).endswith(('.py','.so','.dylib'))}
        installed[name]={'version':expected,'files':files}
    receipt={'runtime_source_commit':identity.source_commit,'guest_sha256':GUEST,
             'host_sha256':digest(host),'host_buildinfo':buildinfo,'go_consumer_sha256':digest(go),
             'system':platform.platform(),'python':sys.version,
             'prototype_files':{f.name:digest(f) for f in sorted(code.iterdir()) if f.is_file()},
             'packages':installed,'runs':{}}
    (evidence/'inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
    for mode in ['control',*MUTATIONS]:
        target=evidence/f'{mode}.json'
        argv=[sys.executable,code/'campaign.py','--host',host,'--go-consumer',go,'--output',target]
        if mode!='control':argv+=['--mutation',mode]
        r=command(argv,mode+'.log')
        if not target.exists():
            receipt['runs'][mode]={'exit':r.returncode,'accepted':False,'reason':'campaign did not produce evidence'}
            continue
        data=json.loads(target.read_text())
        clean=not any(data.get(k) for k in ['fatal','close_errors','uninstall_error']) and data['all_hosts_reaped']
        if mode=='control':
            skipped=[x for x in data['cases'] if x['status']=='SKIP']
            allowed=(not skipped or (a.allow_connector_import_skip and len(skipped)==1 and skipped[0]['name']=='connector-prepared' and data['connector_import_error']))
            accepted=clean and len(data['cases'])==13 and {x['row'] for x in data['cases']}=={f'R{i}' for i in range(1,9)} and not any(x['status']=='FAIL' for x in data['cases']) and bool(allowed) and data['sentinel_attempts']==0
            complete=accepted and not skipped
            receipt['runs'][mode]={'exit':r.returncode,'accepted_for_local_partial':accepted,'complete':complete,'accepted':complete or (a.allow_connector_import_skip and accepted)}
        else:
            failures=[x for x in data['cases'] if x['status']=='FAIL']
            accepted=clean and r.returncode==1 and len(data['cases'])==1 and len(failures)==1 and failures[0]['row']==MUTATIONS[mode]
            # A fatal setup/import/cleanup error is never a successful mutation.
            if mode=='fallback':accepted=accepted and data['sentinel_attempts']>0
            else:accepted=accepted and failures[0]['error_type']=='AssertionError' and data['sentinel_attempts']==0
            receipt['runs'][mode]={'exit':r.returncode,'accepted':accepted,'detected_expected_defect':accepted}
        print(mode,receipt['runs'][mode],flush=True)
    receipt['complete']=receipt['runs']['control'].get('complete',False) and all(x['accepted'] for x in receipt['runs'].values())
    receipt['run_ok']=all(x['accepted'] for x in receipt['runs'].values())
    receipt['evidence']={f.name:digest(f) for f in evidence.iterdir() if f.is_file() and f.name!='inputs.json'}
    (evidence/'inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['run_ok'] else 1

if __name__=='__main__':sys.exit(main())
