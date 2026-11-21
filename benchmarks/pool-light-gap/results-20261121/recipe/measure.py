"""Add counters to checked Git versions of the four generated functions."""
from pathlib import Path
import json
import shutil
import subprocess

def prepare(src,module_src,tmp,rec,h,arm,sha):
    module=h/'period'
    module.mkdir(exist_ok=True)
    shutil.copyfile(rec/'meter.go.txt',module/'meter.go')
    shutil.copyfile(rec/'watch.go.txt',module/'watch.go')
    shutil.copyfile(rec/'detector_test.go.txt',module/'detector_test.go')
    active=400 if arm=='current' else 50
    (module/'period.go').write_text((rec/'period.go.txt').read_text().replace('ACTIVE_PERIOD',str(active)))
    shutil.copyfile(rec/'burst.go.txt',h/'store/burst_test.go')
    fixture=h/'store/fixture_test.go'
    s=fixture.read_text()
    entry='func TestMain(m *testing.M) {'
    assert s.count(entry)==1
    fixture.write_text(s.replace(entry,entry+'\n if os.Getenv("BURST_REPORT")!="" { if err:=burstStudy();err!=nil{fmt.Fprintln(os.Stderr,err);os.Exit(1)}; return }'))
    overlays={}
    for part,num in [(3,16634),(4,16619),(5,16626),(6,16617)]:
        rel=f'internal/generatedgo/code/p{part}/p{part}_pure.go'
        source=subprocess.check_output(['git','show',sha+':'+rel],cwd=src).decode()
        start=source.index(f'func Fn{num}(')
        end=source.index('\n}',start)
        body=source[start:end]
        def after(anchor,code,count):
            nonlocal body
            assert body.count(anchor)==count,(part,anchor)
            body=body.replace(anchor,anchor+'\n'+code)
        if part==3:
            anchor='m.T0[v554].(func(*base.Module, int32, int32, int32))(m, v494, int32(0), v552)'
            assert body.count(anchor)==1
            body=body.replace(anchor,'period.Register(uintptr(m.M),m.Threads,v494); period.Armed(v552)\n'+anchor)
        if part==4:
            after('*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 352, 4))) = int32(1)','period.High(uintptr(m.M))',1)
        if part==5:
            after('func Fn16626(m *base.Module, l0 int32) {','defer period.Tick(uintptr(m.M)).Exit()',1)
            after('*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 352, 4))) = v58','period.Low(uintptr(m.M))',2)
            units=[('v63 * int64(42949672960) >> (uint(int64(32)) % 64) * int64(1000)',1000),('base.I32_wrap_i64(v63) * int32(10)',1)] if arm=='current' else [('int64(4000000)',1000),('int32(4000)',1)]
            for expr,scale in units:
                after(' = '+expr+'\n',f'period.CheckLow(int64({expr})/{scale})\n',2)
        if part==6:
            after('func Fn16617(m *base.Module, l0 int32, l1 int32) {','period.StartWorker()',1)
        source=(source[:start]+body+source[end:]).replace('\nimport (','\nimport (\n period "github.com/shibukawa/pgmem/bench/modelcase/period"',1)
        if part==6:
            a=source.index('func Fn5495(')
            z=source.index('\n}',a)
            handler=source[a:z]
            entry=handler.splitlines()[0]
            handler=handler.replace(entry,entry+'\n defer period.HandlerStart(m.Threads)()',1)
            success='Fn4311(m, int32(27396412), v64)\n\tmBase = m.M\n\tv122 = m.ExcPending'
            assert handler.count(success)==1
            handler=handler.replace(success,success+'\n if v122==0 && v76==12334 {period.Reinsert(uintptr(m.M),v64)}')
            source=source[:a]+handler+source[z:]
        dest=tmp/f'{arm}-p{part}.go'
        dest.write_text(source)
        overlays[str(module_src/rel)]=str(dest)
    overlay=tmp/(arm+'.overlay.json')
    overlay.write_text(json.dumps({'Replace':overlays}))
    return overlay
