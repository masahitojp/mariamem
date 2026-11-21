"""Restore matched PostgreSQL/MariaDB modelcases. Add trace origin and close spans on both."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
w=Path(sys.argv[1]).resolve();mode=sys.argv[2];t=w/'temp';src=w/'worktree';p=w/'evidence/published';rec=p/'recipe'
def git(*args):return subprocess.check_output(['git',*args],cwd=src)
identity=src/'scripts/git_identity.py'
for key,root,sha in [('mariamem',src,'5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c'),('pgmem',t/'pg','a61005d37d01e6671f814fe8ca828222e8147df4')]:
    result=subprocess.check_output([sys.executable,identity,'--root',root,'inspect','HEAD'])
    assert json.loads(result)['source_commit']==sha
    (p/(key+'-source.json')).write_bytes(result)
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=root)
for f in ('overlay.py','pipe.go.txt'):
    assert (rec/f).read_bytes()==git('show','de04aaa7aaf2b8d67c764012111feed6b3d34bac:benchmarks/host-framed-transport/results-20261121/recipe/'+f)
pg=mode=='pg'
commit='bac82de41a87849f23564117825e00fc43b0017a' if pg else '10665616ba6f00d72b5563158a50bfb7cb2305d2'
prefix='benchmarks/modelcase-current/harness/pg-suite/' if pg else 'benchmarks/read-transport/harness/'
h=t/('pg-suite' if pg else mode);h.mkdir(exist_ok=True)
for path in git('ls-tree','-r','--name-only',commit,prefix).decode().splitlines():
    dest=h/path[len(prefix):];dest.parent.mkdir(exist_ok=True,parents=True)
    dest.write_bytes(git('show',commit+':'+path))
if not pg:
    # The standalone CPU probe requires an older diagnostic-only product API.
    # Its test is outside the 70-case modelcase and the semantic checks.
    (h/'store/read_profile_test.go').unlink()
def one(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)
def edit(path,a,b):path.write_text(one(path.read_text(),a,b))
edit(h/'go.mod','<PGMEM_SOURCE>' if pg else '<MARIAMEM_SOURCE>',str(t/'pg' if pg else src))
tr=h/'internal/trace/trace.go'
edit(tr,'"encoding/json"','"encoding/json"\n"strconv"')
edit(tr,'return &Recorder{t0: time.Now(), meta: map[string]string{}}','now:=time.Now();return &Recorder{t0:now, meta:map[string]string{"origin_ns":strconv.FormatInt(now.UnixNano(),10)}}')
f=h/'store/fixture_test.go';s=f.read_text()
s=one(s,'code := m.Run()','code := m.Run()\nfinalClose:=fx.rec.Start("close","close","final")')
s=one(s,'\n\tfx.close()','\n\tfx.close()\nfinalClose()')
s=one(s,'t.Cleanup(func() {','t.Cleanup(func() {\n defer f.rec.Start("close","close",t.Name())()\n')
if pg:
    s=one(s,'pgmem.SnapshotOptions{}','pgmem.SnapshotOptions{MaxForks:16}')
if mode=='frames':
    s=one(s,'"context"','"context"\n"github.com/shibukawa/pgmem/bench/modelcase/frameprobe"')
    s=one(s,'\n\tos.Exit(code)','\n frameprobe.Save()\n\tos.Exit(code)')
f.write_text(s)
env=dict(os.environ,GOTOOLCHAIN='local',GOCACHE=str(t/'gocache'),CGO_ENABLED='0',GOMAXPROCS='8',GOWORK='off',GOFLAGS='',GOPROXY='off',TMPDIR=str(t/'gotmp'))
(t/'gotmp').mkdir(exist_ok=True);args=['go','test','-c','-p','1','-trimpath','-buildvcs=false','-vet=off','-mod=readonly']
if not pg:
    subprocess.run([sys.executable,rec/'overlay.py',w,'raw'],check=True)
    overlay=t/'overlay.json';mp=json.loads(overlay.read_text())['Replace']
    if mode=='frames':
        path=src/'internal/guest/guest.go';data=path.read_text()
        data=one(data,'"encoding/json"','"encoding/json"\n"github.com/shibukawa/pgmem/bench/modelcase/frameprobe"')
        data=one(data,'var decodedAt time.Time','frameprobe.Record(n)\n\t\tvar decodedAt time.Time')
        dest=t/'frame-guest.go';dest.write_text(data);mp[str(path)]=str(dest)
        (h/'frameprobe').mkdir(exist_ok=True);(h/'frameprobe/frames.go').write_bytes((rec/'frame.go.txt').read_bytes())
        overlay=t/'frames-overlay.json';overlay.write_text(json.dumps({'Replace':mp}))
    args+=['-overlay',overlay]
exe=t/(mode+'.test')
subprocess.run(args+['-o',exe,'./store'],cwd=h,env=env,check=True)
(p/(mode+'-binary.json')).write_text(json.dumps(dict(sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),harness_commit=commit,build=subprocess.check_output(['go','version','-m',exe],text=True)),indent=2)+'\n')
