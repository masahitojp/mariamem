from pathlib import Path
import os,sys,subprocess,json,hashlib
w=Path.cwd();t=w/'temp';src=w/'worktree';e=w/'evidence'
arm=sys.argv[1];pg=arm.startswith('pg');diag=arm.endswith('diag')
mod=t/'pg' if pg else src
sha='a61005d37d01e6671f814fe8ca828222e8147df4' if pg else '3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d'
ident=json.loads(subprocess.check_output(['python3',src/'scripts/git_identity.py','--root',mod,'inspect','HEAD']))
assert ident['source_commit']==sha and not subprocess.check_output(['git','status','--porcelain'],cwd=mod)
ref='bac82de41a87849f23564117825e00fc43b0017a' if pg else '10665616ba6f00d72b5563158a50bfb7cb2305d2'
prefix='benchmarks/modelcase-current/harness/pg-suite/' if pg else 'benchmarks/read-transport/harness/'
def git(*args):return subprocess.check_output(['git',*args],cwd=src)
h=t/(arm+'-suite')
for path in git('ls-tree','-r','--name-only',ref,prefix).decode().splitlines():
    if path.endswith('read_profile_test.go'):continue
    dest=h/path[len(prefix):];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(git('show',ref+':'+path))
p=h/'go.mod';p.write_text(p.read_text().replace('<PGMEM_SOURCE>' if pg else '<MARIAMEM_SOURCE>',str(mod)))
if not pg:
    p.write_text(p.read_text().replace('v1.9.3','v1.10.1').replace('v1.1.0','v1.2.0'))
    (h/'go.sum').write_bytes((src/'go.sum').read_bytes())
p=h/'store/fixture_test.go';s=p.read_text()
def replace(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)
s=replace(s,'code := m.Run()','code := m.Run()\nfinalClose:=fx.rec.Start("close","close","final")')
s=replace(s,'\n\tfx.close()','\n\tfx.close()\nfinalClose()')
s=replace(s,'t.Cleanup(func() {','t.Cleanup(func() {\n defer f.rec.Start("close","close",t.Name())()\n')
if pg:s=replace(s,'pgmem.SnapshotOptions{}','pgmem.SnapshotOptions{MaxForks:16}')
p.write_text(s)
if diag:
    p=h/'store/seed.go';s=p.read_text().replace('"fmt"','"fmt"\n"time"\n"encoding/json"'+ ('\n"os"' if pg else ''))
    lo=s.index('func LoadSample(');hi=s.index('\n}',lo);body=s[lo:hi]
    body=replace(body,'tx, err := db.BeginTx','''var ns [7]int64
    var counts [7]int
    var now time.Time
    mark:=func(i int){ ns[i]+=time.Since(now).Nanoseconds();counts[i]++ }
    defer func(){ f,err:=os.OpenFile(os.Getenv("PHASES"),os.O_CREATE|os.O_APPEND|os.O_WRONLY,0600);if err!=nil{panic(err)};defer f.Close();if err=json.NewEncoder(f).Encode([][7]int64{ns,{int64(counts[0]),int64(counts[1]),int64(counts[2]),int64(counts[3]),int64(counts[4]),int64(counts[5]),int64(counts[6])}});err!=nil{panic(err)} }()
    now=time.Now();tx, err := db.BeginTx''')
    body=replace(body,'defer tx.Rollback()','mark(0);defer tx.Rollback();now=time.Now()')
    body=replace(body,'defer reserve.Close()','defer reserve.Close();mark(1)')
    for i,start,end in [(2,'if err := insOrder.Query','if id != o.ID'),(3,'if _, err := insItem.Exec','if _, err := reserve.Exec'),(4,'if _, err := reserve.Exec','\n\t\t}')]:
        body=replace(body,start,'now=time.Now();'+start)
        idx=body.index(end,body.index('now=time.Now();'+start))
        body=body[:idx]+f'\nmark({i});'+body[idx:]
    body=replace(body,'return tx.Commit()','now=time.Now();err=tx.Commit();mark(5);return err')
    p.write_text(s[:lo]+body+s[hi:])
env=dict(os.environ,CGO_ENABLED='0',GOMAXPROCS='8',GOTOOLCHAIN='local',GOCACHE=str(t/'cache'),GOWORK='off',GOPROXY='off',GOFLAGS='',TMPDIR=str(t/'gotmp'))
exe=t/(arm+'.test')
subprocess.run(['go','test','-c','-mod=readonly','-p','2','-trimpath','-buildvcs=false','-vet=off','-o',exe,'./store'],cwd=h,env=env,check=True)
(e/(arm+'-build.json')).write_text(json.dumps(dict(source=ident,harness=ref,sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),go=subprocess.check_output(['go','version','-m',exe],text=True)),indent=2)+'\n')
