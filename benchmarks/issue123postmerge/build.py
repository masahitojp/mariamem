"""Build the same existing lifecycle probe against two clean exact product trees."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[2]
WORK = SOURCE.parent
TEMP, EVIDENCE = WORK / 'temp', WORK / 'evidence'
HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE / 'scripts'))
from git_identity import require_commit


def output(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


plan = json.loads((HARNESS / 'plan.json').read_text())
commit = output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE)
require_commit(SOURCE, commit)
assert not output(['git', 'status', '--porcelain'], cwd=SOURCE)
for arm in ('before', 'after'):
    require_commit(SOURCE, plan[arm])
    assert output(['git', 'cat-file', '-t', plan[arm]], cwd=SOURCE) == 'commit'
assert output(['git', 'rev-parse', plan['after']+'^'], cwd=SOURCE) == plan['before']
sdk_env = dict(os.environ, GOTOOLCHAIN=plan['go'])
sdk = Path(output(['go', 'env', 'GOROOT'], env=sdk_env))
go = str(sdk / 'bin/go')
download_cache = Path(output(['go', 'env', 'GOMODCACHE'], env=sdk_env))/'cache/download'
env = {k:v for k,v in os.environ.items() if not k.startswith(('GO', 'MARIAMEM_', 'MYSQLMEM_'))}
env.update(GOTOOLCHAIN='local', GOWORK='off', GOENV='off', CGO_ENABLED='0',
           GOCACHE=str(TEMP/'gocache'), GOPATH=str(TEMP/'gopath'),
           GOMODCACHE=str(TEMP/'modcache'), GOMAXPROCS='4', GOMEMLIMIT='3GiB', GOGC='50',
           GOPROXY=download_cache.as_uri()+',https://proxy.golang.org', GOSUMDB='sum.golang.org')
version = output([go, 'version'], env=env)
assert version.startswith('go version '+plan['go']+' ')
inputs = {'harness_source_commit':commit, 'go':version, 'binaries':{},
          'harness_files':{str(p.relative_to(HARNESS)):digest(p) for p in HARNESS.rglob('*') if p.is_file()},
          'product_sources':{}, 'build_flags':['-trimpath','-p','1','-buildvcs=false']}
for arm in ('before', 'after'):
    checkout = TEMP / arm
    subprocess.run(['git','worktree','add','--detach',str(checkout),plan[arm]], cwd=SOURCE, check=True)
    assert not output(['git','status','--porcelain'],cwd=checkout)
    inputs['product_sources'][arm] = {'source_commit':plan[arm],
        'tree':output(['git','rev-parse','HEAD^{tree}'],cwd=checkout),
        'inputs':{name:digest(checkout/name) for name in
                  ('go.mod','go.sum','guest/input.json','release/generated-go-inputs.json','internal/generatedgo/provenance.json')}}
    module=TEMP/(arm+'-probe'); module.mkdir()
    for name in ('maria','probe'):
        shutil.copytree(HARNESS/name,module/name)
    (module/'go.mod').write_text('module github.com/masahitojp/mariamem/benchmarks/issue123baseline\n\ngo 1.26.0\n\nrequire (\n github.com/masahitojp/mariamem v0.0.0\n github.com/go-sql-driver/mysql v1.9.3\n)\nrequire filippo.io/edwards25519 v1.1.0 // indirect\n\nreplace github.com/masahitojp/mariamem => '+str(checkout)+'\n')
    shutil.copyfile(checkout/'go.sum',module/'go.sum')
    binary=TEMP/('bin-'+arm)
    print('Building '+arm+' '+plan[arm],flush=True)
    with (TEMP/(arm+'-build.txt')).open('w') as log:
        subprocess.run([go,'build','-trimpath','-p','1','-buildvcs=false','-o',str(binary),'./maria'],
                       cwd=module,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
    inputs['binaries'][arm]={'sha256':digest(binary),'build_info':output([go,'version','-m',str(binary)]).replace(str(WORK),'<WORKSPACE>')}
    assert not output(['git','status','--porcelain'],cwd=checkout)
    print('Built '+arm,flush=True)
assert inputs['product_sources']['before']['inputs']['guest/input.json']==inputs['product_sources']['after']['inputs']['guest/input.json']
assert inputs['product_sources']['before']['inputs']['release/generated-go-inputs.json']==inputs['product_sources']['after']['inputs']['release/generated-go-inputs.json']
(EVIDENCE/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
