"""Instrument exact branches, preserving the guest queue and locking operations."""
import shutil

def prepare(code,h,rec,edit,one):
    shutil.copyfile(rec/'worker.go.txt', h/'p8probe/worker.go')
    def patch(pkg,n,pairs):
        def apply(src):
            a=src.index('func Fn'+str(n)+'(')
            z=src.index('\n}',a)
            body=src[a:z]
            for anchor,stmt in pairs:
                body=one(body,anchor,stmt)
            return src[:a]+body+src[z:]
        edit(code/pkg/(pkg+'_pure.go'),apply)
    def event(kind,worker='0',x='0',y='0',pool='l0'):
        return f'm.Threads.Probe.Event({kind},{pool},{worker},&m.ProbeAgent,int64({x}),int64({y}))'
    def before(anchor,stmt):return anchor,stmt+'\n'+anchor
    def after(anchor,stmt):return anchor,anchor+'\n'+stmt
    # Both circular-queue insertion paths call the same wake policy under the lock.
    def scope_submit(src):
        a='m.Threads.Probe.Enqueue(l1,m.ProbeAgent)\n Fn16618(m, l0)'
        assert src.count(a)==2
        return src.replace(a,'m.ProbeAgent.SubmitStamp=m.Threads.Probe.Enqueue(l1,m.ProbeAgent)\n Fn16618(m, l0)\n m.ProbeAgent.SubmitStamp=0')
    edit(code/'p7/p7_pure.go',scope_submit)
    patch('p7',16618,[
        after('if v5 == v6 {',event(1)),
        after('if base.Ui32(v8) < base.Ui32(v9-(v10+v11)) {',event(2,x='v8',y='v9-(v10+v11)')),
        before('Fn16578(m, v16)',event(3,'v16')),
        before('Fn16619(m, l0)',event(4))])
    patch('p4',16619,[
        after('if base.Ui32(v18) <= base.Ui32(v17) {',event(5,x='v17',y='v18')),
        after('if v55-v57 < v74 {',event(6,x='v55-v57',y='v74')),
        after('if v83&v81 != 0 {',event(7)),
        before('v196 = Fn16620(m,',event(8,'v157'))])
    patch('p6',16617,[
        after('func Fn16617(m *base.Module, l0 int32, l1 int32) {','m.ProbeAgent.Pool=l0;m.ProbeAgent.Worker=l1;'+event(9,'l1')),
        after('m.T0[v47].(func(*base.Module, int32))(m, v43)',event(14,'l1','v43'))])
    wait='Fn16581(m, l1, v14+int32(8), v153)'
    patch('p4',16616,[
        after('*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 156, 4))) = v279',event(12,'l1','v268')),
        (wait,'m.ProbeAgent.CondWait=true;'+event(10,'l1')+'\n'+wait+'\n'+event(11,'l1')+';m.ProbeAgent.CondWait=false')])
    patch('p5',16626,[after('func Fn16626(m *base.Module, l0 int32) {','m.Threads.Probe.Event(19,l0,0,&m.ProbeAgent,0,0);m.ProbeAgent.Maintenance=true;defer func(){m.ProbeAgent.Maintenance=false}()')])
    patch('p5',17633,[
        after('func Fn17633(m *base.Module, l0 int32) int32 {','previous:=m.ProbeAgent.DblStamp;defer func(){m.ProbeAgent.DblStamp=previous}()'),
        after('v160 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v33)), 0, 4)))','m.ProbeAgent.DblStamp=probe.Now()')])
    # p5 gains its first probe import via this generated file.
    p=code/'p5/p5_pure.go'
    edit(p,lambda s: one(s,'\nimport (','\nimport (\nprobe "github.com/shibukawa/pgmem/bench/modelcase/p8probe"'))
