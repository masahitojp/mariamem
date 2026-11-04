from pathlib import Path
import os,subprocess,json,hashlib,re
w=Path(__file__).resolve().parents[1];t=w/'temp';e=w/'evidence';s=t/'source';env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),GOTMPDIR=str(t/'go-tmp'))
cmd=['/opt/homebrew/bin/go','build','-p','1','-mod=mod','-trimpath','-buildvcs=false','-o',str(t/'copy-probe'),'.']
with (e/'copy-probe-build.log').open('w') as log:subprocess.run(cmd,cwd=t/'copyprobe',env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
(e/'copy-probe-build.json').write_text(json.dumps({'binary_sha256':hashlib.sha256((t/'copy-probe').read_bytes()).hexdigest(),'main_source_sha256':hashlib.sha256((e/'copy_main.go').read_bytes()).hexdigest(),'source_commit':json.loads((e/'host-stage.json').read_text())['source_commit'],'go_buildinfo':subprocess.check_output(['/opt/homebrew/bin/go','version','-m',str(t/'copy-probe')],env=env,text=True)},indent=2)+'\n');print('standalone actual MemoryInit probe built')
