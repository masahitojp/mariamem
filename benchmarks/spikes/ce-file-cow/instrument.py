"""Exact-baseline experimental overlay; not canonical generated source."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = "a8137b8b444f86068d3128a291e3a848adfdfd56"
GOFMT = os.environ["GOFMT"]
changes = {}

def read(name):
    p = ROOT / name
    old = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT)
    assert p.read_bytes() == old, "Unexpected preimage: " + name
    changes[name] = {"before": hashlib.sha256(old).hexdigest()}
    return old.decode()

def save(name, text):
    (ROOT / name).write_text(text)

name = "internal/generatedgo/code/base/base.go"
s = read(name)
s = s.replace("type MemFS struct {", "type MemFS struct {\n e *eProbe\n ceRecords []ceRecord", 1)
s = s.replace("type memNode struct {", "type memNode struct {\n e *eBacking\n ce *ceShared", 1)
needle = "\t\tparent.children[base] = node\n"
assert s.count(needle) == 1
s = s.replace(needle, needle+"\t\tfsys.eEnroll(node)\n")
old = """\tcp := make([]byte, len(data))
\tcopy(cp, data)
\tparent.children[base] = &memNode{parent: parent, name: base, mode: perm & 0o777, modTime: time.Now(), data: cp}
"""
new = """\tnode := &memNode{parent: parent, name: base, mode: perm & 0o777, modTime: time.Now()}
\tfsys.eEnroll(node)
\tnode.data = fsys.eResize(node, int64(len(data)))
\tcopy(node.data, data)
\tparent.children[base] = node
"""
assert old in s
s = s.replace(old,new)
assert s.count("resizeMemData(f.node.data, end)") == 2
s = s.replace("resizeMemData(f.node.data, end)", "f.fsys.eResize(f.node, end)")
assert s.count("resizeMemData(f.node.data, size)") == 1
s = s.replace("resizeMemData(f.node.data, size)", "f.fsys.eResize(f.node, size)")
s=s.replace('if flag&os.O_TRUNC != 0 && !node.dir {', 'if flag&os.O_TRUNC != 0 && !node.dir {\n if node.ce!=nil {node.ceRelease();node.data=nil}')
s=s.replace('end := off + int64(len(p))', 'end := off + int64(len(p))\n if len(p)>0 {f.fsys.ceOwn(f.node,end,"write")}')
save(name,s)

name="internal/generatedgo/code/base/owned_prepared.go"
s=read(name)
s=s.replace('p := &PreparedFiles{}','p := &PreparedFiles{}\n ce:=os.Getenv("MARIAMEM_CE")=="1"')
s=s.replace('var data []byte','var data []byte\n index:=-1\n prot:=syscall.PROT_READ|syscall.PROT_WRITE\n if ce {prot=syscall.PROT_READ}')
s=s.replace('syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_PRIVATE','prot, syscall.MAP_PRIVATE')
s=s.replace('p.mappings = append(p.mappings, data)','index=len(p.mappings)\n p.mappings = append(p.mappings, data)')
s=s.replace('node.data = data','node.data = data\n if ce {node.ce=&ceShared{p,index}}')
save(name,s)
name="internal/generatedgo/code/base/prepared_files.go"
s=read(name).replace('for _, data := range p.mappings {','for _, data := range p.mappings {\n if data==nil {continue}')
save(name,s)

name = "internal/generatedgo/runtime_instance.go"
s = read(name)
s = s.replace("\t\tfs := base.NewMemFS()",
"""\t\tfs := base.NewMemFS()
\t\tif restore == nil {
\t\t\tif err = fs.EProbeEnable(); err != nil { return }
\t\t}
\t\tdefer func(){err = errors.Join(err, fs.CEReport(restore!=nil))}()\n\t\tdefer func(){err = errors.Join(err, fs.EProbeClose())}()
""")
s = s.replace("\t\tif transfer != \"\" {", "\t\tif err = fs.EProbeAudit(); err != nil { return }\n\t\tif transfer != \"\" {")
s = s.replace("\t\tif err = fs.EProbeAudit();", "\t\tif handled, e := fs.EHandoff(transfer, GuestSHA256); handled { err=e; return }\n\t\tif err = fs.EProbeAudit();")
save(name,s)

name = "internal/host/server.go"
s = read(name)
s = s.replace("type Server struct {", "type Server struct {\n eDirect bool",1)
s = s.replace("s := &Server{Guest:", 's := &Server{eDirect: restore == nil && os.Getenv("MARIAMEM_E_MODE")=="handoff", Guest:',1)
needle = "\ttiming.Mark(ctx, \"preconditions_destination_ready\")\n"
assert s.count(needle)==1
s=s.replace(needle,needle+"""\tif s.eDirect {
        if err=os.WriteFile(filepath.Join(s.transfer,".e-request"),nil,0600);err!=nil {s.mu.Unlock();return false,err}
    }
""")
s=s.replace("if err = s.finish(ctx, true);", 'if err = s.finish(ctx, !s.eDirect || os.Getenv("MARIAMEM_E_AUDIT")=="1");',1)
s=s.replace("err = snapshot.PublishContext(ctx, s.transfer, path, s.build)","""if s.eDirect {
        err = snapshot.PublishSharedExperimental(ctx,s.transfer,path,s.build)
    } else { err = snapshot.PublishContext(ctx, s.transfer, path, s.build) }""",1)
save(name,s)

for src,dst in [("ce.go.txt","ce_file.go"),("ce_test.go.txt","ce_file_test.go"),("observer.go.txt","e_backing.go"),("observer_test.go.txt","e_backing_test.go"),("handoff.go.txt","e_handoff.go"),("handoff_test.go.txt","e_handoff_test.go")]:
    name="internal/generatedgo/code/base/"+dst
    assert not (ROOT/name).exists()
    changes[name]={"before":None}
    (ROOT/name).write_bytes((HERE/src).read_bytes())
for src,dst in [("publish.go.txt","e_publish.go")]:
    name="internal/snapshot/"+dst
    assert not (ROOT/name).exists()
    changes[name]={"before":None}
    (ROOT/name).write_bytes((HERE/src).read_bytes())
subprocess.run([GOFMT,"-w",*[str(ROOT/n) for n in changes]],check=True)
for name, item in changes.items():
    item["after"]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
(HERE/"instrumentation.json").write_text(json.dumps(changes,indent=2)+"\n")
