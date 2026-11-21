"""Add timer-specific observations after the unchanged previous probes."""
import shutil
from pathlib import Path

def install(source,part):
    def function(num,edit):
        nonlocal source
        a=source.index(f'func Fn{num}(')
        b=source.index('\n}',a)
        source=source[:a]+edit(source[a:b])+source[b:]
    def mark(kind,addr,value,domain):
        return f'period.Mark(m.Threads,uintptr(m.M),"{kind}",{addr},int64({value}),\'{domain}\')'
    def around(s,anchor,before='',after=''):
        assert s.count(anchor)==1,anchor
        return s.replace(anchor,'\n'.join(x for x in (before,anchor,after) if x))
    def entry(num,addr,domain,name,value='0'):
        def edit(s):
            anchor=s.splitlines()[0]
            return around(s,anchor,after=mark(name+'_enter',addr,value,domain)+'\ndefer func(){'+mark(name+'_return',addr,'m.ExcPending',domain)+'}()')
        function(num,edit)
    if part==3:
        function(16634,lambda s:around(s,'period.Register(uintptr(m.M));',after='period.Bind(m.Threads,uintptr(m.M),period.LatestID(),v13,v494);'))
    if part==5:
        entry(16626,'l0','p','maintenance')
    if part==6:
        def handler(s):
            s=around(s,s.splitlines()[0],after='period.ThreadStart(m.Threads);defer func(){'+mark('handler_return','0','m.ExcPending','g')+'}()')
            def pair(anchor,name,addr,before,after,domain='d'):
                nonlocal s
                s=around(s,anchor,mark(name,addr,before,domain),mark(name+'_done',addr,after,domain))
            # v11 is the private copy of the earliest queued wall-clock deadline.
            wait='v152 = Fn216(m, int32(27396476), int32(27396448), v11)'
            due='*(*int64)(unsafe.Add(mBase,base.MemoryEA(m,uint64(uint32(v11)),0,8)))*1000000000 + int64(*(*int32)(unsafe.Add(mBase,base.MemoryEA(m,uint64(uint32(v11)),8,4)))) - v53'
            pair(wait,'wait','v133',due,'v152')
            pair('v79 = Fn4313(m, int32(27396412), v72)','pop','v64','v74','m.ExcPending')
            pair('m.T0[v76].(func(*base.Module, int32))(m, v75)','dispatch','v64','v76','m.ExcPending')
            pair('Fn4311(m, int32(27396412), v64)','reinsert','v64','v109','m.ExcPending')
            s=around(s,'if v74 == int64(0) {',before=mark('old_period_us','v64','v74','h'))
            s=around(s,'if v85 == int64(0) {',before=mark('new_period_us','v64','v85','h'))
            return s
        function(5495,handler)
        entry(5497,'l0','h','schedule','l1')
    if part==7:
        entry(16625,'l0','t','execute')
        entry(16638,'l0','t','arm','l2')
        entry(16639,'l0','t','disarm')
    if part==8:
        entry(5498,'l0','h','cancel')
        entry(16636,'l0','t','submit_worker_task')
    return source
