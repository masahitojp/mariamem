from pathlib import Path
import subprocess,os,json,hashlib,time
E=Path(__file__).resolve().parent;T=E.parent/'temp'
env=dict(os.environ,GOTOOLCHAIN='local',GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'),GOTMPDIR=str(T/'tmp'))
records=json.loads((E/'binaries.json').read_text()) if (E/'binaries.json').exists() else {}
for name,module,target,test in [('pgmem-suite','pg-suite','./store',True),('pgmem-lifecycle','lifecycle','./postgres',False),('mariamem-suite','maria-suite','./store',True),('mariamem-lifecycle','lifecycle','./maria',False)]:
 if os.environ.get('BENCH_BUILD_ONLY') and os.environ['BENCH_BUILD_ONLY']!=name:continue
 cmd=['go','test' if test else 'build','-p','1','-trimpath','-buildvcs=false']+(['-c'] if test else [])+['-o',str(T/'bin'/name),target]
 at=time.monotonic();print('BUILD',name,flush=True)
 with (E/(name+'-build.txt')).open('w') as log:subprocess.run(cmd,cwd=T/module,env=env,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
 binary=T/'bin'/name
 records[name]={'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'seconds':time.monotonic()-at,'command':cmd,'buildinfo':subprocess.check_output(['go','version','-m',str(binary)],text=True,env=env)}
 (E/'binaries.json').write_text(json.dumps(records,indent=2)+'\n')
 print('PASS',name,flush=True)
