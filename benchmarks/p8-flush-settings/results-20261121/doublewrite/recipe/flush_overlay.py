"""Stamp the page, file and simulated-AIO boundaries in generated Go."""
import re
import shutil
def prepare(code, h, rec, edit, one):
    shutil.copyfile(rec/'flush.go.txt',h/'p8probe/flush.go')
    def hook(pkg,n,stmt,imports=False,anchor=None):
        def apply(s):
            start=s.index('func Fn'+str(n)+'(')
            end=s.index('\n}',start)
            body=s[start:end]
            if anchor is None:
                line=body.splitlines()[0]
            else:line=anchor
            return s[:start]+one(body,line,line+'\n'+stmt)+s[end:]
        edit(code/pkg/(pkg+'_pure.go'),apply,imports)
    hook('p2',17933,'old:=m.ProbeAgent.Cleaner; m.ProbeAgent.Cleaner=true;defer func(){m.ProbeAgent.Cleaner=old}()')
    for pkg,n,imports in [('p4',17935,True),('p3',17936,False)]:
        hook(pkg,n,'old,fn:=m.ProbeAgent.Batch,m.ProbeAgent.BatchFn;m.ProbeAgent.Batch=probe.Now();m.ProbeAgent.BatchFn='+str(n)+';defer func(){m.ProbeAgent.Batch,m.ProbeAgent.BatchFn=old,fn}()',imports)
    hook('p4',17922,'m.Threads.Probe.BeginFlush(l0,*(*uint64)(unsafe.Add(m.M,base.MemoryEA(m,uint64(uint32(l0)),0,8))),m.ProbeAgent)')
    hook('p4',17922,'m.Threads.Probe.Buffered(l0,v701,v701+1,uint32(v706))',anchor='*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v711)), 12, 4))) = v705 | int32(4)')
    hook('p5',17872,'prev:=m.ProbeAgent.IO;m.ProbeAgent.IO=m.Threads.Probe.FileIO(l6,l3,m.ProbeAgent.WriteAt!=0);defer func(){m.ProbeAgent.IO=prev}()')
    hook('p8',17874,'prev:=m.ProbeAgent.IO;m.ProbeAgent.IO.Submit=probe.Now();m.ProbeAgent.IO.Control=uint32(l1);defer func(){m.ProbeAgent.IO=prev}()',True)
    hook('p3',17914,'m.Threads.Probe.CompletePage(&m.ProbeAgent,v94)',anchor='v94 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v18)), 0, 4)))')
    def fixture(s):
        a='db := openInProcess(s)';s=one(s,a,a+'\n probe.Configure(ctx,db,t.Name())')
        a='db := openInProcess(srv)\n\t\t\tdone :='
        return one(s,a,a.replace('done :=','probe.Configure(ctx,db,"shared")\n done :='))
    edit(h/'store/fixture_test.go',fixture)
