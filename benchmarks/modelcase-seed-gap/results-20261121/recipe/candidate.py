from pathlib import Path
import os,subprocess,json,shutil,hashlib,sys
from run import run,names
w=Path.cwd();t=w/'temp';e=w/'evidence'
env={k:os.environ[k] for k in ('PATH','HOME')};env.update(GOMODCACHE=subprocess.check_output(['go','env','GOMODCACHE'],text=True).strip(),GOGC='100',GOMAXPROCS='8',TMPDIR=str(t/'gotmp'),MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0',SKIP_READ_BODY='0',TRANSPORT_DIAG='0',CGO_ENABLED='0',GOCACHE=str(t/'cache'),GOWORK='off',GOTOOLCHAIN='local',GOPROXY='off',GOFLAGS='')
def checked(args,**kwargs):
    r=subprocess.run(args,env=env,capture_output=True,timeout=300,**kwargs)
    if r.returncode:raise RuntimeError(str(args)+' '+(r.stdout+r.stderr)[-2000:].decode())
    return r.stdout
if sys.argv[1]=='train':
    profiles=[]
    for i in range(4):
        path=t/f'train-{i}.pprof';profiles.append(path)
        log=checked([t/'maria.test','-test.v','-test.parallel=1','-test.run=^Test('+'|'.join(names)+')$','-test.cpuprofile='+str(path)])
        assert b'PASS' in log and b'--- SKIP:' not in log
    (e/'training.pprof').write_bytes(checked(['go','tool','pprof','-proto',*profiles]))
elif sys.argv[1]=='build':
    for name in ('pgcheck','normal','pgo'):
        src=t/('pg-suite' if name=='pgcheck' else 'maria-suite')
        shutil.copyfile(e/'recipe/seed_check.go.txt',src/'store/seed_oracle_test.go')
        opt='-pgo='+str(e/'training.pprof') if name=='pgo' else '-pgo=off'
        exe=t/(name+'.test')
        checked(['go','test','-c','-p','2','-mod=readonly','-trimpath','-buildvcs=false','-vet=off',opt,'-o',exe,'./store'],cwd=src)
        (e/(name+'-binary.json')).write_text(json.dumps(dict(sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),pgo=opt.split('/')[-1],build=checked(['go','version','-m',exe]).decode()),indent=2)+'\n')
elif sys.argv[1]=='measure':
    for a in ('pgcheck','normal','pgo'):
        log=checked([t/(a+'.test'),'-test.run=^TestSeedOracle$','-test.v'])
        assert b'--- PASS: TestSeedOracle' in log
        (e/(a+'-oracle.log')).write_bytes(log)
    for a in ('normal','pgo'):
        for p in (1,8):run(a,'pre',0,0,p)
    for b in range(1,7):
        order=('normal','pgo','normal') if b%2 else ('pgo','normal','pgo')
        for p in ((1,8) if b%2 else (8,1)):
            for i,a in enumerate(order):run(a,'candidate',b,i,p)
