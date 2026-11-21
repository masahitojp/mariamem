"""Use the identical period selector in the diagnostic and ordinary P8 binaries."""
from pathlib import Path
import hashlib
import json
import shutil

def prepare(w,h,mp,mode):
    out=w/'evidence/study'
    package=h/'period'
    package.mkdir(exist_ok=True)
    shutil.copyfile(out/'recipe/period.go.txt',package/'period.go')
    p=w/'worktree/internal/generatedgo/code/p3/p3_pure.go'
    fixture=h/'store/fixture_test.go'
    changes={}
    def patch(path, transform):
        source=Path(mp.get(str(path),path)).read_text()
        data=transform(source)
        if 'bench/modelcase/period"' not in data:data=data.replace('\nimport (','\nimport (\n period "github.com/shibukawa/pgmem/bench/modelcase/period"',1)
        dest=w/'temp'/(mode+'-period-'+path.name)
        dest.write_text(data)
        mp[str(path)]=str(dest)
        changes[path.name]=[changes.get(path.name, [hashlib.sha256(source.encode()).hexdigest()])[0], hashlib.sha256(data.encode()).hexdigest()]
    def replace(s,a,b):
        assert s.count(a)==1,a
        return s.replace(a,b)
    def constructor(s):
        begin=s.index('func Fn16634(');end=s.index('\n}',begin)
        body=s[begin:end]
        old='*(*int64)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v13)), 216, 8))) = int64(400)'
        body=replace(body,old,old.replace('int64(400)','period.Milliseconds'))
        arm='m.T0[v554].(func(*base.Module, int32, int32, int32))(m, v494, int32(0), v552)'
        body=replace(body,arm,('period.Register(uintptr(m.M))\n ' if mode=='idle' else '')+'period.Armed(v552)\n '+arm)
        return s[:begin]+body+s[end:]
    patch(p,constructor)
    pool = w/'worktree/internal/generatedgo/code/p5/p5_pure.go'
    def separate_idle(s):
        start = s.index('func Fn16626(')
        end = s.index('\n}', start)
        body = s[start:end]
        load = 'v63 = *(*int64)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 216, 8)))'
        assert body.count(load) == 2
        body = body.replace(load, load + '\n if period.Split { v63 = 400 }')
        if mode == 'idle':
            for symbol, unit in [('v63 * int64(42949672960) >> (uint(int64(32)) % 64) * int64(1000)', '1000'), ('base.I32_wrap_i64(v63) * int32(10)', '1')]:
                assert body.count(' = ' + symbol + '\n') == 2
                body = body.replace(' = ' + symbol + '\n', ' = ' + symbol + '\n period.CheckLow(int64(' + symbol + ')/' + unit + ')\n')
        return s[:start] + body + s[end:]
    patch(pool, separate_idle)
    patch(fixture,lambda s:replace(s,'os.Exit(code)','period.Report();os.Exit(code)'))
    if mode=='idle':
        shutil.copyfile(out/'recipe/meter.go.txt', package/'meter.go')
        shutil.copyfile(out/'recipe/idle_test.go.txt',h/'store/idle_study_test.go')
        def add_entry(s):
            # The fixture already imports period. patch() adds the import only
            # on the first modification of each file.
            a='func TestMain(m *testing.M) {'
            return replace(s,a,a+'\nif os.Getenv("IDLE_DBS")!="" {if err:=holdIdle();err!=nil{fmt.Fprintln(os.Stderr,err);os.Exit(1)};return}')
        dest=Path(mp[str(fixture)])
        data=add_entry(dest.read_text())
        dest.write_text(data);changes[fixture.name][1]=hashlib.sha256(data.encode()).hexdigest()
        def hook(pkg,num,anchor,extra,count):
            f=w/'worktree/internal/generatedgo/code'/pkg/(pkg+'_pure.go')
            def transform(s):
                a=s.index('func Fn'+str(num)+'(');z=s.index('\n}',a)
                part=s[a:z];assert part.count(anchor)==count,(num,anchor)
                return s[:a]+part.replace(anchor,anchor+'\n'+extra)+s[z:]
            patch(f,transform)
        hook('p5',16626,'func Fn16626(m *base.Module, l0 int32) {','period.Tick(uintptr(m.M))',1)
        hook('p5',16626,'*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 352, 4))) = v58','period.Low(uintptr(m.M))',2)
        hook('p4',16619,'*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 352, 4))) = int32(1)','period.High(uintptr(m.M))',1)
        hook('p6',16617,'func Fn16617(m *base.Module, l0 int32, l1 int32) {','period.StartWorker()',1)
    (out/(mode+'-period-bindings.json')).write_text(json.dumps(changes,indent=2)+'\n')
    return mp
