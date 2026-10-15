"""Exact-baseline experimental overlay; not canonical generated source."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = "a8137b8b444f86068d3128a291e3a848adfdfd56"
GOFMT = "/Users/masahito/.go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.8.darwin-arm64/bin/gofmt"
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
s = s.replace("type MemFS struct {", "type MemFS struct {\n e *eProbe", 1)
s = s.replace("type memNode struct {", "type memNode struct {\n e *eBacking", 1)
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
save(name,s)

name = "internal/generatedgo/runtime_instance.go"
s = read(name)
s = s.replace("\t\tfs := base.NewMemFS()",
"""\t\tfs := base.NewMemFS()
\t\tif restore == nil {
\t\t\tif err = fs.EProbeEnable(); err != nil { return }
\t\t}
\t\tdefer func(){err = errors.Join(err, fs.EProbeClose())}()
""")
s = s.replace("\t\tif transfer != \"\" {", "\t\tif err = fs.EProbeAudit(); err != nil { return }\n\t\tif transfer != \"\" {")
save(name,s)

for src,dst in [("observer.go.txt","e_backing.go"),("observer_test.go.txt","e_backing_test.go")]:
    name="internal/generatedgo/code/base/"+dst
    assert not (ROOT/name).exists()
    changes[name]={"before":None}
    (ROOT/name).write_bytes((HERE/src).read_bytes())
subprocess.run([GOFMT,"-w",*[str(ROOT/n) for n in changes]],check=True)
for name, item in changes.items():
    item["after"]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
(HERE/"instrumentation.json").write_text(json.dumps(changes,indent=2)+"\n")
