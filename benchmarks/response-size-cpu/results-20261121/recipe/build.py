"""Run from the experiment root. All generated inputs live in temp/."""
from pathlib import Path
import os,sys,subprocess,json
w=Path.cwd(); root=w/'worktree'; tmp=w/'temp'
def git(ref,path):
    return subprocess.check_output(['git','show',ref+':'+path],cwd=root,text=True)
ring='a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb'
base='be12aeb6ebed61f291d98ffa08b872a03695900b'
for ref in (ring,base):
    assert json.loads(subprocess.check_output(['python3',root/'scripts/git_identity.py','--root',root,'inspect',ref]))['source_commit']==ref
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==ring
for arm in sys.argv[1:]:
    diag=arm.endswith('-diag')
    ref=base if arm.startswith('os') else ring
    changes={}
    def put(path,body):
        target=tmp/(arm+'-'+Path(path).name)
        target.write_text(body)
        changes[str(root/path)]=str(target)
    bench='tests/gointegration/large_response_test.go'
    b=git(ring,bench).replace('"fmt"','"fmt"\n"os"\n"strconv"\n"runtime/pprof"')
    b=b.replace('const clients = 8','size, err := strconv.Atoi(os.Getenv("PAYLOAD")); if err!=nil || size<=0 || size%2!=0 {b.Fatal("bad payload")}\n const clients = 8')
    b=b.replace('131072)','size/2)',1).replace('"SELECT CONCAT(?, REPEAT(?,131072))"', 'fmt.Sprintf("SELECT CONCAT(?, REPEAT(?,%d))",len(payload)/2)')
    b=b.replace('before := cpuTime()', '''if name:=os.Getenv("PROFILE"); name!="" { f,err:=os.Create(name); if err!=nil {b.Fatal(err)}; defer f.Close(); if err=pprof.StartCPUProfile(f);err!=nil {b.Fatal(err)}; defer pprof.StopCPUProfile() }
    before := cpuTime()''')
    linked='internal/guest/linked.go'
    link=git(ref,linked)
    if diag:
        b=b.replace('"fmt"','"fmt"\n"github.com/masahitojp/mariamem/internal/guest"').replace('before := cpuTime()','startCounts:=guest.ProbeCounts(); before := cpuTime()').replace('b.StopTimer()','b.StopTimer(); endCounts:=guest.ProbeCounts(); for i,k:=range []string{"reads","writes","wire-read-B","wire-write-B","full-waits","nonempty-copies","copy-B"} {b.ReportMetric(float64(endCounts[i]-startCounts[i])/float64(b.N),k)}')
        link=link.replace('"fmt"','"fmt"\n"sync/atomic"')
        link+='''
var probe [7]atomic.Uint64
func ProbeCounts()(v [7]uint64){for i:=range v {v[i]=probe[i].Load()};return}
type probeReader struct{io.ReadCloser}
func(r probeReader)Read(p []byte)(int,error){n,e:=r.ReadCloser.Read(p);probe[0].Add(1);probe[2].Add(uint64(n));return n,e}
type probeWriter struct{io.WriteCloser}
func(w probeWriter)Write(p []byte)(int,error){n,e:=w.WriteCloser.Write(p);probe[1].Add(1);probe[3].Add(uint64(n));return n,e}
'''
        link=link.replace('childIn, childOut, logs','childIn, probeWriter{childOut}, logs').replace('ctx, in, out, execution','ctx, in, probeReader{out}, execution')
        if ref==ring:
            path='internal/guest/byte_pipe.go'
            link=link.replace('out, childOut := newBytePipe()','out, childOut := newBytePipe(); out.p.response=true')
            p=git(ring,path).replace('type bytePipe struct {','type bytePipe struct {\nresponse bool')
            p=p.replace('if p.used == len(p.buf) {','if p.used == len(p.buf) {\nif p.response {probe[4].Add(1)}')
            for anchor in ('p.used -= n','p.used += n'):
                p=p.replace(anchor,'if p.response {probe[6].Add(uint64(n));probe[5].Add(1);if first<n {probe[5].Add(1)}}\n'+anchor)
            put(path,p)
    put(bench,b);put(linked,link)
    overlay=tmp/(arm+'.json');overlay.write_text(json.dumps({'Replace':changes}))
    env=dict(os.environ,GOCACHE=str(tmp/'cache'),GOTMPDIR=str(tmp/'gotmp'),GOPROXY='off',GOMAXPROCS='8')
    subprocess.run(['go','test','-c','-p','2','-vet=off','-trimpath','-tags=integration','-overlay',overlay,'-o',tmp/arm,'./tests/gointegration'],cwd=root,env=env,check=True)
    print(arm,'built',flush=True)
