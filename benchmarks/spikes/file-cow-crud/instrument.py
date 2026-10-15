"""Install a measurement overlay into an isolated checkout, never canonical source."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'a8137b8b444f86068d3128a291e3a848adfdfd56'
records = []

def edit(name, replacements):
    p = ROOT / name
    before = p.read_bytes()
    expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', SOURCE + ':' + name])
    if before != expected:
        raise ValueError('unexpected complete preimage: ' + name)
    s = before.decode()
    for a, b, count in replacements:
        if s.count(a) != count:
            raise ValueError((name, a, s.count(a), count))
        s = s.replace(a, b)
    p.write_text(s)
    subprocess.run(['gofmt', '-w', str(p)], check=True)
    records.append({'path': name, 'before_sha256': hashlib.sha256(before).hexdigest(),
                    'after_sha256': hashlib.sha256(p.read_bytes()).hexdigest()})

edit('internal/generatedgo/code/base/base.go', [
 ('root *memNode\n}', 'root *memNode\n cow *cowAudit\n}', 1),
 ('children map[string]*memNode\n}', 'children map[string]*memNode\n cow *cowNode\n}', 1),
 ('node.data = node.data[:0]', 'fsys.cowTouch(node,"open-truncate",0,0)\n node.data = node.data[:0]', 1),
 ('func (f *memFile) writeAt(p []byte, off int64) int {', 'func (f *memFile) writeAt(p []byte, off int64) int {\n f.fsys.cowTouch(f.node,"write",off+int64(len(p)),len(p))', 1),
 ('func (f *memFile) Allocate(end int64) error {', 'func (f *memFile) Allocate(end int64) error {', 1),
 ('if end > int64(len(f.node.data)) {\n\t\tf.node.data = resizeMemData(f.node.data, end)\n\t\tf.node.modTime', 'if end > int64(len(f.node.data)) {\n f.fsys.cowTouch(f.node,"allocate",end,0)\n\t\tf.node.data = resizeMemData(f.node.data, end)\n\t\tf.node.modTime', 1),
 ('f.node.data = resizeMemData(f.node.data, size)', 'f.fsys.cowTouch(f.node,"truncate",size,0)\n f.node.data = resizeMemData(f.node.data, size)', 1),
])
edit('internal/generatedgo/code/base/owned_prepared.go', [
 ('node.data = data', 'node.data = data\n fsys.cowMap(node)', 1),
])
edit('internal/generatedgo/runtime_instance.go', [
 ('fs := base.NewMemFS()', 'fs := base.NewMemFS()\n role:="fresh";if restore!=nil{role="fork"}\n fs.CowAuditBegin(role)\n defer fs.CowAuditEnd()', 1),
])
for source, dest in [('observer.go.txt','cow_observer.go'), ('observer_test.go.txt','cow_observer_test.go')]:
    p=ROOT/'internal/generatedgo/code/base'/dest
    if p.exists(): raise ValueError('overlay file already exists')
    p.write_bytes(Path(__file__).with_name(source).read_bytes())
    subprocess.run(['gofmt','-w',str(p)],check=True)
    records.append({'path':str(p.relative_to(ROOT)), 'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
Path(__file__).with_name('instrumentation.json').write_text(json.dumps(records,indent=2)+'\n')
