from pathlib import Path
import os,sys,subprocess,json,hashlib
w=Path.cwd();t=w/'temp';src=w/'worktree';e=w/'evidence'
arm=sys.argv[1];assert arm in ('perf','observed')
mod=src
sha='3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d'
ident=json.loads(subprocess.check_output(['python3',src/'scripts/git_identity.py','--root',mod,'inspect','HEAD']))
assert ident['source_commit']==sha and not subprocess.check_output(['git','status','--porcelain'],cwd=mod)
ref='10665616ba6f00d72b5563158a50bfb7cb2305d2'
prefix='benchmarks/read-transport/harness/'
def git(*args):return subprocess.check_output(['git',*args],cwd=src)
h=t/(arm+'-suite')
for path in git('ls-tree','-r','--name-only',ref,prefix).decode().splitlines():
    if path.endswith('read_profile_test.go'):continue
    dest=h/path[len(prefix):];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(git('show',ref+':'+path))
(h/'store/charset_reserve_test.go').write_bytes((e/'recipe/catalog.go.txt').read_bytes())
p=h/'go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(mod)))
p.write_text(p.read_text().replace('v1.9.3','v1.10.1').replace('v1.1.0','v1.2.0'))
(h/'go.sum').write_bytes((src/'go.sum').read_bytes())
p=h/'store/fixture_test.go';s=p.read_text()
def replace(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)
s=replace(s,'code := m.Run()','code := m.Run()\nfinalClose:=fx.rec.Start("close","close","final")')
s=replace(s,'\n\tfx.close()','\n\tfx.close()\nfinalClose()')
s=replace(s,'t.Cleanup(func() {','t.Cleanup(func() {\n defer f.rec.Start("close","close",t.Name())()\n')
p.write_text(s)
env=dict(os.environ,CGO_ENABLED='0',GOMAXPROCS='8',GOTOOLCHAIN='local',GOCACHE=str(t/'cache'),GOWORK='off',GOPROXY='off',GOFLAGS='',TMPDIR=str(t/'gotmp'))
exe=t/(arm+'.test')
opts=['-overlay',str(t/('overlay.json' if arm=='observed' else 'perf-overlay.json'))]
subprocess.run(['go','test','-c',*opts,'-mod=readonly','-p','2','-trimpath','-buildvcs=false','-vet=off','-o',exe,'./store'],cwd=h,env=env,check=True)
(e/(arm+'-build.json')).write_text(json.dumps(dict(source=ident,harness=ref,sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),go=subprocess.check_output(['go','version','-m',exe],text=True)),indent=2)+'\n')
