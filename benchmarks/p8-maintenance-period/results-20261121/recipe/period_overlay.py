"""Use the identical period selector in the diagnostic and ordinary P8 binaries."""
from pathlib import Path
import hashlib
import json
import shutil

def prepare(w,h,mp,mode):
    out=w/'evidence/timer'
    package=h/'period'
    package.mkdir(exist_ok=True)
    shutil.copyfile(out/'recipe/period.go.txt',package/'period.go')
    p=w/'worktree/internal/generatedgo/code/p3/p3_pure.go'
    fixture=h/'store/fixture_test.go'
    changes={}
    def patch(path, transform):
        source=Path(mp.get(str(path),path)).read_text()
        data=transform(source).replace('\nimport (','\nimport (\n period "github.com/shibukawa/pgmem/bench/modelcase/period"',1)
        dest=w/'temp'/(mode+'-period-'+path.name)
        dest.write_text(data)
        mp[str(path)]=str(dest)
        changes[path.name]=[hashlib.sha256(x.encode()).hexdigest() for x in (source,data)]
    def replace(s,a,b):
        assert s.count(a)==1,a
        return s.replace(a,b)
    def constructor(s):
        begin=s.index('func Fn16634(');end=s.index('\n}',begin)
        body=s[begin:end]
        old='*(*int64)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v13)), 216, 8))) = int64(400)'
        body=replace(body,old,old.replace('int64(400)','period.Milliseconds'))
        arm='m.T0[v554].(func(*base.Module, int32, int32, int32))(m, v494, int32(0), v552)'
        body=replace(body,arm,'period.Armed(v552)\n '+arm)
        return s[:begin]+body+s[end:]
    patch(p,constructor)
    patch(fixture,lambda s:replace(s,'os.Exit(code)','period.Report();os.Exit(code)'))
    (out/(mode+'-period-bindings.json')).write_text(json.dumps(changes,indent=2)+'\n')
    return mp
