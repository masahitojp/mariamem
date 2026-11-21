"""Restore the pinned harness and build an instrumented Darwin/arm64 binary."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

recipe = Path(__file__).resolve().parent
workspace = Path(sys.argv[1]).resolve()
source, temp = workspace / 'worktree', workspace / 'temp'
harness = temp / 'harness'
assert json.loads(subprocess.check_output(
    ['python3', 'scripts/git_identity.py', 'inspect', 'HEAD'], cwd=source
))['source_commit'] == '5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c'
prior = '7c5893b3d5198d2c5087dbb100e631dfe63a58bb:'
restore_path = 'benchmarks/trigger-sum-bottleneck/results-20261121/recipe/restore.py'
for name in ['restore.py','main.go']:
    (temp/name).write_bytes(subprocess.check_output(
        ['git','show',prior+str(Path(restore_path).with_name(name))],cwd=source))
subprocess.run([sys.executable,temp/'restore.py',harness,source],check=True)
pkg = harness/'pageprobe'
pkg.mkdir(exist_ok=True)
for name in ['trace.go','page.go']:
    shutil.copy2(recipe/name,pkg/name)

def change(text,old,new):
    assert text.count(old)==1, old
    return text.replace(old,new)

probe = '"github.com/shibukawa/pgmem/bench/modelcase/pageprobe"'
main = harness/'main.go'
s = change(main.read_text(),'import (','import (\n'+probe)
s = change(s,'start := time.Now()','ordinal := 0\n start := time.Now()')
s = change(s,'_, err = st.Exec','pageprobe.Begin(n,ordinal); ordinal++\n _, err = st.Exec')
s = change(s,'it.UnitPriceCents)\n\t\t\tmust(err)','it.UnitPriceCents)\n pageprobe.Reply()\n must(err)')
s = change(s,'flag.Parse(); run()','flag.Parse(); pageprobe.Start(); run(); pageprobe.Save()')
s = change(s,'time.Now().After(deadline)','i+1 >= 8 && time.Now().After(deadline)')
main.write_text(s)

overlay = temp/'overlay'
overlay.mkdir(exist_ok=True)
files = {}
def save(path,data):
    dest = overlay/path.name
    dest.write_text(data)
    files[str(path)] = str(dest)

code = source/'internal/generatedgo/code'
base = code/'base/base.go'
s = change(base.read_text(),'\nimport (','\nimport (\n'+probe)
struct, = re.findall(r'type Module struct \{.*?\n\}', s, re.S)
s = change(s,struct,struct[:-1]+'Trace *pageprobe.Request\n}')
save(base,change(s,'*child = *m','*child = *m\n child.Trace=nil'))

# The fixed binary has one direct append site in Fn14079. Mark each alloc_root
# call site explicitly, since both logical sizes can equal eight.
entries = {
    5581:'if m.Trace!=nil {panic("nested SQL")}; m.Trace=pageprobe.Enter(); defer func(){m.Trace=nil}()',
    15566:('Trigger','true',''),
    14079:('Plan','true','r.Frame.Arena=l2; if r.Frame.Trigger {r.Mark("plan")}'),
    20087:('Key','pageprobe.CString(m.Memory,l2)','if r.Frame.Plan && r.Frame.Trigger {r.Mark("append")}'),
    783:('Root','l1','r.Frame.SameArena=r.Frame.Arena==l0; if r.Frame.Plan && r.Frame.Trigger && r.Frame.SameArena {r.Mark("root")}'),
    986:('My','l0',''),
    236:('Wrap','l0',''),
    152:('DL','l0','if r.Frame.Plan && r.Frame.Trigger && r.Frame.SameArena {r.Mark("dlmalloc")}'),
}
store = '*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v737)), 4, 4))) = v738 | int32(1)'
seen=set()
for path in sorted(code.glob('p*/*_pure.go')):
    s=path.read_text()
    if not any(f'func Fn{i}(' in s for i in entries): continue
    for i,entry in entries.items():
        pattern=rf'(?m)^func Fn{i}\([^\n]+?\{{'
        matches=list(re.finditer(pattern,s))
        if not matches: continue
        assert len(matches)==1 and i not in seen
        seen.add(i)
        if isinstance(entry,tuple):
            field,value,action=entry
            entry=(f'if r:=m.Trace; r!=nil {{old:=r.Frame; r.Frame.{field}={value}; {action}; '
                   'defer func(){r.Frame=old}()}')
        at=matches[0].end()
        s=s[:at]+'\n'+entry+s[at:]
    if 'func Fn14079(' in s:
        call='v227 = Fn20087(m, l3+int32(212), l2, v226)'
        s=change(s,call,'if r:=m.Trace; r!=nil {r.Frame.Possible=true}\n'+call+
                 '\nif r:=m.Trace; r!=nil {r.Frame.Possible=false}')
    if 'func Fn20087(' in s:
        start=s.index('func Fn20087(')
        end=s.index('\n}',start)+2
        body=s[start:end]
        for marker,site in [('v11 = Fn783(m, l1, v10)','string'),('v17 = Fn783(m, l1, int32(8))','list_node')]:
            body=change(body,marker,'if r:=m.Trace; r!=nil && r.Frame.Plan && r.Frame.Trigger {r.Frame.Site="'+site+'"}\n'+marker)
        s=s[:start]+body+s[end:]
    if 'func Fn152(' in s:
        s=change(s,store,'if r:=m.Trace; r!=nil { r.Store(mBase,base.MemoryEA(m,uint64(uint32(v737)),4,4),v738|int32(1)) } else {'+store+'}')
    if 'pageprobe.' in s: s=change(s,'\nimport (','\nimport (\n'+probe)
    save(path,s)
assert seen==set(entries)
manifest=overlay/'overlay.json'
manifest.write_text(json.dumps({'Replace':files}))
env=dict(os.environ, CGO_ENABLED='1',GOMAXPROCS='8',GOCACHE=str(temp/'gocache'),
         GOTOOLCHAIN='local',GOWORK='off',GOPROXY='off',GOFLAGS='',TMPDIR=str(temp/'gotmp'))
(temp/'gotmp').mkdir(exist_ok=True)
subprocess.run(['go','build','-trimpath','-buildvcs=false','-p','1','-mod=readonly',
                '-overlay',manifest,'-o',temp/'probe','.'],cwd=harness,env=env,check=True)
