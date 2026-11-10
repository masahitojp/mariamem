"""Build one external harness against a clean, identity-checked product tree."""
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
require_commit(SOURCE, plan['product_source_commit'])
assert not output(['git', 'status', '--porcelain'], cwd=SOURCE)
changed = output(['git', 'diff', '--name-only', plan['product_source_commit'], commit], cwd=SOURCE).splitlines()
assert changed and all(p.startswith('benchmarks/issue101overlap/') for p in changed), changed
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
module = TEMP/'probe'
module.mkdir()
for d in ('maria','probe'): shutil.copytree(HARNESS/d,module/d)
(module/'go.mod').write_text('module github.com/masahitojp/mariamem/benchmarks/issue101runner\n\ngo 1.26.0\n\nrequire (\n github.com/masahitojp/mariamem v0.0.0\n github.com/go-sql-driver/mysql v1.9.3\n)\n\nreplace github.com/masahitojp/mariamem => '+str(SOURCE)+'\n')
with (TEMP/'build.txt').open('w') as log:
    for args in ([go,'mod','tidy'],[go,'test','-count=1','./probe'],[go,'test','-race','-count=1','./probe'],[go,'build','-trimpath','-p','1','-buildvcs=false','-o',str(TEMP/'bin'),'./maria']):
        local=dict(env)
        if '-race' in args: local['CGO_ENABLED']='1'
        subprocess.run(args,cwd=module,env=local,stdout=log,stderr=subprocess.STDOUT,check=True)
inputs=dict(harness_source_commit=commit,product_source_commit=plan['product_source_commit'],product_tree=output(['git','rev-parse',plan['product_source_commit']+'^{tree}'],cwd=SOURCE),go=version,
            binary_sha256=digest(TEMP/'bin'),build_flags=['-trimpath','-p','1','-buildvcs=false'],
            harness_files={str(p.relative_to(HARNESS)):digest(p) for p in HARNESS.rglob('*') if p.is_file()},
            product_inputs={n:digest(SOURCE/n) for n in ['guest/input.json','release/generated-go-inputs.json','internal/generatedgo/provenance.json','go.mod','go.sum']},
            module_files={n:(module/n).read_text().replace(str(SOURCE),'<SOURCE>') for n in ['go.mod','go.sum']},
            build_info=output([go,'version','-m',str(TEMP/'bin')]).replace(str(WORK),'<WORKSPACE>'))
(EVIDENCE/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
(EVIDENCE/'build-controls.txt').write_text((TEMP/'build.txt').read_text().replace(str(WORK),'<WORKSPACE>'))
print('BUILD and barrier unit/race controls PASS',flush=True)
