"""Exact-preimage experimental instrumentation; no canonical provenance changes."""
from pathlib import Path
import hashlib,json,subprocess

repo=Path(__file__).resolve().parents[3]
base=repo/'internal/generatedgo/code/base'
records=[]
def edit(path, replacements):
 old=path.read_text();new=old
 expected=subprocess.check_output(['git','-C',str(repo),'show','a8137b8b444f86068d3128a291e3a848adfdfd56:'+str(path.relative_to(repo))])
 assert path.read_bytes()==expected,('unexpected full preimage',path)
 for before,after,count in replacements:
  assert new.count(before)==count,(path,before,new.count(before))
  new=new.replace(before,after)
 path.write_text(new)
 records.append(dict(path=str(path.relative_to(repo)),before_sha256=hashlib.sha256(old.encode()).hexdigest(),after_sha256=hashlib.sha256(new.encode()).hexdigest()))

edit(base/'base.go',[
 ('root *memNode\n}', 'root *memNode\n auditID uint64\n auditRole string\n}',1),
 ('children map[string]*memNode\n}', 'children map[string]*memNode\n audit *AuditNode\n}',1),
 ('dirOff   int\n}', 'dirOff   int\n auditClosed bool\n}',1),
 ('node.data = node.data[:0]', 'fsys.auditTrunc(node)\n node.data = node.data[:0]',1),
 ('f := &memFile{fsys:', 'fsys.auditOpen(node)\n f := &memFile{fsys:',1),
 ('delete(parent.children, base)\n\treturn nil', 'fsys.auditUnlink(n)\n delete(parent.children, base)\n\treturn nil',1),
 ('np.children[nb] = node\n\treturn nil','np.children[nb] = node\n fsys.auditRename(node)\n\treturn nil',1),
 ('parent.children[base] = &memNode{parent: parent, name: base, mode: perm & 0o777, modTime: time.Now(), data: cp}', 'if old:=parent.children[base];old!=nil{fsys.auditUnlink(old)}\n parent.children[base] = &memNode{parent: parent, name: base, mode: perm & 0o777, modTime: time.Now(), data: cp}\n fsys.auditPopulate(parent.children[base])',1),
 ('f.node.data = resizeMemData(f.node.data, end)', 'f.fsys.auditResize(f.node, end, "allocate")',2),
 ('if end > int64(len(f.node.data)) {','f.fsys.auditRequest(f.node,end)\n if end > int64(len(f.node.data)) {',2),
 ('func (f *memFile) Close() error { return nil }','func (f *memFile) Close() error { f.auditClose(); return nil }',1),
 ('n := copy(p, f.node.data[f.off:])','n := copy(p, f.node.data[f.off:])\n f.fsys.auditIO(f.node,int(f.off),n,false)',1),
 ('n := copy(p, f.node.data[off:])','n := copy(p, f.node.data[off:])\n f.fsys.auditIO(f.node,int(off),n,false)',1),
 ('copy(f.node.data[off:], p)','copy(f.node.data[off:], p)\n f.fsys.auditIO(f.node,int(off),len(p),true)',1),
 ('f.node.data = resizeMemData(f.node.data, size)','f.fsys.auditResize(f.node, size, "truncate")',1),
])
# The two end-growth sites have distinct owners. Correct the write path label.
p=base/'base.go';s=p.read_text();start=s.index('func (f *memFile) writeAt(');end=s.index('\nfunc (f *memFile) Write(',start)
s=s[:start]+s[start:end].replace('end, "allocate"','end, "write-grow"').replace('f.fsys.auditRequest(f.node,end)\n ','')+s[end:];p.write_text(s)
records[0]['after_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
edit(base/'owned_prepared.go',[('node.data = data','node.data = data\n fsys.auditMap(node)',1)])
edit(repo/'internal/generatedgo/runtime_instance.go',[
 ('fs := base.NewMemFS()','fs := base.NewMemFS()\n if restore!=nil {fs.AuditRole("fork")} else {fs.AuditRole("fresh")}\n defer fs.AuditEnd()',1),
 ('err = exportTransfer(fs, transfer)','base.AuditPhase("host-export")\n err = exportTransfer(fs, transfer)',1),
])
edit(repo/'benchmarks/ownedprepared/main.go',[
 ('"github.com/masahitojp/mariamem"','"github.com/masahitojp/mariamem"\n auditbase "github.com/masahitojp/mariamem/internal/generatedgo/code/base"',1),
 ('measure := func(name string, f func()) {','measure := func(name string, f func()) {\n phase:=name\n switch {case strings.HasPrefix(name,"fresh_ready")||name=="prepare_start":phase="fresh-ready";case strings.HasPrefix(name,"fresh_setup")||name=="prepare_setup":phase="fixture-sql";case name=="snapshot":phase="guest-snapshot";case strings.HasPrefix(name,"fork_ready"):phase="fork-ready";case strings.HasPrefix(name,"child_close"):phase="close";default:phase="child-sql"}\n auditbase.AuditPhase(phase)',1),
 ('elapsed, consumed := time.Since(t).Seconds(), cpu()-c','elapsed, consumed := time.Since(t).Seconds(), cpu()-c\n auditbase.AuditCheckpoint(name)',1),
 ('must(os.WriteFile(*out, b, 0600))','must(os.WriteFile(*out, b, 0600))\n if path:=os.Getenv("MARIAMEM_MEMFS_AUDIT_OUT");path!=""{must(auditbase.AuditSave(path))}',1),
])
target=base/'memfs_audit.go';target.write_bytes(Path(__file__).with_name('observer.go.txt').read_bytes())
test=base/'memfs_audit_test.go';test.write_bytes(Path(__file__).with_name('observer_test.go.txt').read_bytes())
subprocess.run(['gofmt','-w',str(base/'base.go'),str(base/'owned_prepared.go'),str(target),str(test),str(repo/'internal/generatedgo/runtime_instance.go'),str(repo/'benchmarks/ownedprepared/main.go')],check=True)
for r in records:r['after_sha256']=hashlib.sha256((repo/r['path']).read_bytes()).hexdigest()
records.append(dict(path=str(target.relative_to(repo)),before_sha256=None,after_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
records.append(dict(path=str(test.relative_to(repo)),before_sha256=None,after_sha256=hashlib.sha256(test.read_bytes()).hexdigest()))
Path(__file__).with_name('instrumentation-inputs.json').write_text(json.dumps(records,indent=2)+'\n')
print('Applied exact-preimage experiment instrumentation; canonical guard is intentionally not claimed')
