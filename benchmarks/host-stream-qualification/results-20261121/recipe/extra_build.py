from pathlib import Path
import subprocess,json,os,sys
w=Path(sys.argv[1]).resolve();t=w/'temp';src=w/'worktree';rec=Path(__file__).resolve().parent
assert json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=src))['source_commit']=='5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c'
mapping=json.loads((t/'fault-overlay.json').read_bytes())['Replace']
p=src/'internal/guest/guest.go';s=p.read_text()
assert s.count('complete <- writeAll(p.in, b)')==1
s=s.replace('complete <- writeAll(p.in, b)','complete <- p.qualWrite(b)')
s+='''
type qualGate struct { sent, release chan struct{}; once sync.Once }
var qualGates sync.Map
func(p *Process) QualPartial() (<-chan struct{},func()) {
 g:=&qualGate{sent:make(chan struct{}),release:make(chan struct{})};qualGates.Store(p,g)
 return g.sent,func(){g.once.Do(func(){close(g.release)})}
}
func(p *Process) qualWrite(b []byte) error {
 if len(b)>16384 {
   if entry,ok:=qualGates.LoadAndDelete(p);ok{
     g:=entry.(*qualGate)
     if err:=writeAll(p.in,b[:16384]);err!=nil{return err};close(g.sent);<-g.release
     return writeAll(p.in,b[16384:])
   }
 }
 return writeAll(p.in,b)
}
'''
modified=t/'extra-guest.go';modified.write_text(s);mapping[str(p)]=str(modified)
mapping[str(src/'internal/host/qual_extra_test.go')]=str(rec/'extra_test.go.txt')
o=t/'extra-overlay.json';o.write_text(json.dumps({'Replace':mapping}))
env=dict(os.environ,CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'gocache'),GOTOOLCHAIN='local',GOWORK='off',GOPROXY='off',GOFLAGS='',TMPDIR=str(t/'gotmp'))
subprocess.run(['go','test','-c','-trimpath','-vet=off','-p','1','-overlay',o,'-o',t/'extra.test','./internal/host'],cwd=src,env=env,check=True)
