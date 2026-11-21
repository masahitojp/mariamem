"""Patch exact Go sites in the disposable build only."""
import hashlib,json,shutil
from pathlib import Path

def prepare(w,h,mp,arm):
    src=w/'worktree';rec=Path(__file__).resolve().parent
    pkg=h/'p8probe';pkg.mkdir(exist_ok=True)
    for f in ('probe','client'):shutil.copyfile(rec/(f+'.go.txt'),pkg/(f+'.go'))
    dst=w/'temp'/('src-'+arm);dst.mkdir(exist_ok=True)
    bindings={}
    def edit(path,fn,imp=False):
        p=Path(mp.get(str(path),path));s=p.read_text()
        data=fn(s)
        if imp:data=one(data,'\nimport (','\nimport (\nprobe "github.com/shibukawa/pgmem/bench/modelcase/p8probe"')
        dest=dst/(str(path.relative_to(w)).replace('/','_'))
        dest.write_text(data);mp[str(path)]=str(dest)
        key=str(path.relative_to(w));bindings[key]=[bindings[key][0] if key in bindings else hashlib.sha256(s.encode()).hexdigest(),hashlib.sha256(data.encode()).hexdigest()]
    def one(s,a,b):
        assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
    def repl(path,a,b,imp=False):edit(path,lambda s:one(s,a,b),imp)
    repl(src/'internal/guest/linked.go','capture := &prepared.Capture{}','ctx=probe.Bind(ctx,transfer)\n capture := &prepared.Capture{}',True)
    repl(src/'internal/guest/linked.go','p := &Process{startupTiming:', 'p := &Process{diag:probe.From(ctx),startupTiming:')
    def host(s):
        s=one(s,'type Process struct {','type Process struct {\n diag *probe.DB')
        s=one(s,'p.pending[id] = ch','p.pending[id] = ch\n measured:=p.diag.Call(id,slot,op)')
        return one(s,'case r := <-ch:\n\t\treturn r.result, r.err','case r := <-ch:\n measured.Resume=probe.Now();return r.result,r.err')
    edit(src/'internal/guest/guest.go',host,True)
    repl(src/'internal/generatedgo/runtime_instance.go','m, release = created, ownedRelease','m, release = created, ownedRelease\n m.Threads.Probe=probe.Lookup(transfer)',True)
    code=src/'internal/generatedgo/code'
    def base(s):
        # Preserve all existing offsets in Module, including the gcasm bridge.
        i=s.index('\n}',s.index('type Module struct {'));s=s[:i]+'\n ProbeAgent probe.Agent'+s[i:]
        s=one(s,'parked map[uint64][]chan struct{}','parked map[uint64][]chan struct{}\n Probe *probe.DB\n observed map[chan struct{}]*probe.Wait')
        s=one(s,'*child = *m','*child = *m\n child.ProbeAgent=probe.Agent{TID:tid}')
        s=one(s,'return m.Threads.wake(AtomicEA(m, addr, offset, 4), count)','return m.Threads.wake(AtomicEA(m, addr, offset, 4), count,m.ProbeAgent)')
        s=one(s,'func (p *ThreadPool) wake(ea uint64, count int32)', 'func (p *ThreadPool) wake(ea uint64, count int32, source probe.Agent)')
        s=one(s,'for _, ch := range waiters[:n] {\n\t\tclose(ch)','for _, ch := range waiters[:n] {\n if w:=p.observed[ch];w!=nil{w.Notify(source)}\n close(ch)')
        a=s.index('func AtomicWait(m ');b=s.index('\n}',a)+2;body=s[a:b]
        body=one(body,'m.Threads.parked[ea] = append(m.Threads.parked[ea], ch)', '''var event *probe.Wait
    if m.Threads.Probe!=nil{
        if m.Threads.observed==nil{m.Threads.observed=map[chan struct{}]*probe.Wait{}}
        event=m.Threads.Probe.Park(ea,timeout,m.ProbeAgent);m.Threads.observed[ch]=event
    }
    m.Threads.parked[ea] = append(m.Threads.parked[ea], ch)''')
        body=one(body,'defer m.Threads.parkMu.Unlock()','defer m.Threads.parkMu.Unlock()\n delete(m.Threads.observed,ch)')
        body=one(body,'defer unpark()','defer func(){unpark();if event!=nil{m.Threads.Probe.Finish(event)}}()')
        for target,branch in [('ch','notify'),('m.Threads.failureDone()','failure'),('timer.C','timeout')]:
            label='case <-'+target+':';assert body.count(label)==(1 if branch=='timeout' else 2)
            body=body.replace(label,label+'\n if event!=nil{event.Selected=probe.Now();event.Branch="'+branch+'"}')
        return s[:a]+body+s[b:]
    edit(code/'base/base.go',base,True)
    repl(code/'p1/p1_pure.go','v169 = Fn130(m, v85)','v169 = Fn130(m, v85)\n m.ProbeAgent.Request=uint32(v167);m.ProbeAgent.WorkerAt=probe.Now()',True)
    repl(code/'p6/p6_pure.go','func Fn265(m *base.Module, l0 int32, l1 int32, l2 int32) {','func Fn265(m *base.Module, l0 int32, l1 int32, l2 int32) {\n m.Threads.Probe.Reply(uint32(l0),uint32(l1));if m.ProbeAgent.Request==uint32(l0){m.ProbeAgent.Request=0;m.ProbeAgent.WorkerAt=0}')
    p=code/'p7/p7_pure.go'
    def queue(s):
        a=s.index('func Fn16628(');b=s.index('\n}',a)
        old='Fn16618(m, l0)';body=s[a:b];assert body.count(old)==2
        return s[:a]+body.replace(old,'m.Threads.Probe.Enqueue(l1,m.ProbeAgent)\n '+old)+s[b:]
    edit(p,queue)
    p=code/'p6/p6_pure.go'
    def dispatch(s):
        a=s.index('func Fn16608(');b=s.index('\n}',a);body=s[a:b]
        for code,task,arg in [('v132','l0','v131'),('v71','v58','v70')]:
            call='m.T0['+code+'].(func(*base.Module, int32))(m, '+arg+')'
            body=one(body,call,'{previous:=m.Threads.Probe.Invoke('+task+','+arg+',&m.ProbeAgent)\n'+call+'\nm.ProbeAgent.Current=previous}')
        return s[:a]+body+s[b:]
    edit(p,dispatch)
    for file,num,field in [('p7',16625,'TimerAt'),('p7',17875,'AIOAt'),('p3',17914,'WriteAt')]:
        p=code/file/(file+'_pure.go')
        a='func Fn'+str(num)+'(m *base.Module, l0 int32) {'
        extra='m.ProbeAgent.WriteArg=uint32(l0);' if field=='WriteAt' else ''
        repl(p,a,a+'\n old:=m.ProbeAgent.'+field+';m.ProbeAgent.'+field+'=probe.Now();'+extra+'defer func(){m.ProbeAgent.'+field+'=old}()',file=='p3' or num==16625)
    tr=h/'internal/trace/trace.go'
    edit(tr,lambda s:one(one(s,'"encoding/json"','"encoding/json"\n"strconv"'),'return &Recorder{t0: time.Now(), meta: map[string]string{}}','now:=time.Now();return &Recorder{t0:now,meta:map[string]string{"probe_ns":strconv.FormatInt(probe.Stamp(now),10)}}'),True)
    # Reuse the previous verified client_operation and sample-lane instrumentation.
    pre='d78ed430ab50ca90cfe38f57ba7bb024a5a95fde:benchmarks/host-stream-p8-attribution/results-20261121/recipe/overlay.py'
    import subprocess
    old=subprocess.check_output(['git','show',pre],cwd=src,text=True)
    section=old[old.index("    edit(h/'store/fixture_test.go'"):old.index("    (w/'evidence/published'")]
    def prior_edit(path,pairs):
        def transform(s):
            for a,b in pairs:s=one(s,a,b)
            return s
        edit(path,transform,True)
    from textwrap import dedent
    exec(dedent(section),dict(h=h,edit=prior_edit))
    import flush_overlay
    flush_overlay.prepare(code,h,rec,edit,one)
    import worker_overlay
    worker_overlay.prepare(code,h,rec,edit,one)
    (w/'evidence/doublewrite'/('bindings-'+arm+'.json')).write_text(json.dumps(bindings,indent=2)+'\n')
    return mp
