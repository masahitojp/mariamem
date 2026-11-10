"""One toolchain, pinned product sources, unchanged shop SQL/oracles."""
from pathlib import Path
import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile

S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence';H=Path(__file__).resolve().parent
sys.path.insert(0,str(S/'scripts'))
from git_identity import require_commit,read_release_pin,verify_release_pin,ReleasePin

def out(args,**kw):return subprocess.check_output(args,text=True,**kw).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=json.loads((H/'plan.json').read_text());head=out(['git','rev-parse','HEAD'],cwd=S)
require_commit(S,head);require_commit(S,p['source_commit']);baseline=read_release_pin(S/p['baseline_pin']);verify_release_pin(S,baseline)
assert not out(['git','status','--porcelain'],cwd=S)
changes=out(['git','diff','--name-only',p['source_commit'],head],cwd=S).splitlines()
assert all(n.startswith('benchmarks/shopcurrentp8/') or n==p['baseline_pin'] for n in changes),changes
pg=T/'pgmem'
print('Acquire pinned pgmem1.18.2',flush=True)
with (T/'acquisition.txt').open('w') as log:
 subprocess.run(['git','clone','--depth','1','--single-branch','--branch','v1.18.2','https://github.com/shibukawa/pgmem.git',str(pg)],stdout=log,stderr=subprocess.STDOUT,check=True)
verify_release_pin(pg,ReleasePin(**p['pgmem']));require_commit(pg,p['pgmem']['source_commit'])
assert out(['git','rev-parse','HEAD'],cwd=pg)==p['pgmem']['source_commit'] and not out(['git','status','--porcelain'],cwd=pg)
archive=T/'v062.tar';subprocess.run(['git','archive','--format=tar','--output',str(archive),baseline.source_commit],cwd=S,check=True)
archive_sha=sha(archive);old=T/'v062';old.mkdir()
with tarfile.open(archive) as tf:
 assert all(not x.name.startswith('/') and '..' not in Path(x.name).parts and (x.isfile() or x.isdir()) for x in tf.getmembers())
 tf.extractall(old)
archive.unlink()
sdk_env=dict(os.environ,GOTOOLCHAIN=p['go']);go=str(Path(out(['go','env','GOROOT'],env=sdk_env))/'bin/go')
cache=Path(out(['go','env','GOMODCACHE'],env=sdk_env))/'cache/download'
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_'))}
env.update(GOTOOLCHAIN='local',GOENV='off',GOWORK='off',CGO_ENABLED='0',GOCACHE=str(T/'gocache'),GOPATH=str(T/'gopath'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='4',GOMEMLIMIT='3GiB',GOGC='50',GOPROXY=cache.as_uri()+',https://proxy.golang.org',GOSUMDB='sum.golang.org')
version=out([go,'version'],env=env);assert version=='go version '+p['go']+' darwin/arm64'
inputs=dict(harness_source_commit=head,product_source_commit=p['source_commit'],baseline=dataclasses.asdict(baseline),pgmem=p['pgmem'],go=version,baseline_archive_sha256=archive_sha,binaries={},harness_files={str(f.relative_to(H)):sha(f) for f in H.rglob('*') if f.is_file()},build_flags=['-trimpath','-buildvcs=false','-mod=readonly','-p1'],product_inputs={arm:{n:sha(src/n) for n in ['guest/input.json','release/generated-go-inputs.json','internal/generatedgo/provenance.json','go.mod','go.sum']} for arm,src in [('v062',old),('current',S)]})
for arm in p['arms']:
 module=T/(arm+'-runner');module.mkdir()
 for name in ['internal','maria','postgres']:shutil.copytree(H/name,module/name)
 text=(H/'go.mod').read_text().replace('replace github.com/masahitojp/mariamem => ../..','replace github.com/masahitojp/mariamem => '+str(old if arm=='v062' else S)).replace('replace github.com/shibukawa/pgmem => ../../../temp/pgmem','replace github.com/shibukawa/pgmem => '+str(pg))
 (module/'go.mod').write_text(text);shutil.copyfile(H/'go.sum',module/'go.sum')
 package='./postgres/store' if arm=='pgmem' else './maria/store'
 print('BUILD '+arm,flush=True)
 with (T/(arm+'-build.txt')).open('w') as log:
  subprocess.run([go,'test','-c','-trimpath','-p','1','-buildvcs=false','-mod=readonly','-o',str(T/('bin-'+arm)),package],cwd=module,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 info=out([go,'version','-m',str(T/('bin-'+arm))]).replace(str(W),'<WORKSPACE>')
 inputs['binaries'][arm]=dict(sha256=sha(T/('bin-'+arm)),build_info=info,module_sha256=sha(module/'go.mod'),source_commit=p['pgmem']['source_commit'] if arm=='pgmem' else baseline.source_commit if arm=='v062' else p['source_commit'])
 (E/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
 print('BUILT '+arm,flush=True)
assert not out(['git','status','--porcelain'],cwd=S)
