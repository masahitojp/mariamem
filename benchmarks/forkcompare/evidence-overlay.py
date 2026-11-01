"""Single-binary experiment overlay: argv selection and existing guest timing file access."""
import hashlib,json
from pathlib import Path
B=Path(__file__).resolve().parent;W=B.parents[2];P=W/'temp/product';O=W/'temp/overlay';O.mkdir(parents=True,exist_ok=True)
files={
 'internal/generatedgo/code/experiment_read_io.go':(B/'candidate-data.go.txt').read_text(),
 'internal/timing/experiment_guest_source.go':(B/'guest-filebridge.go.txt').read_text(),
 'internal/generatedgo/code/base/diag_sql_wake.go':'package base\nimport "os"\nfunc DiagBegin(m *Module,kind string,a,b,c int64)func(){return func(){}}\nfunc DiagDump(path string)error{return os.WriteFile(path,[]byte("{}\\n"),0600)}\n'
}
p='internal/timing/timing.go';s=(P/p).read_text();old='data, err := os.ReadFile(filepath.Join(transfer, "startup-timing.json"))';assert s.count(old)==1
files[p]=s.replace(old,old+'\n if err!=nil{data,err=experimentReadGuest(transfer)}')
p='internal/generatedgo/runtime_instance.go';s=(P/p).read_text();s=s.replace('"sync"','"sync"\n "os"\n "github.com/masahitojp/mariamem/internal/timing"')
old='w.SetFS(entropyFS{fs})';assert s.count(old)==1
files[p]=s.replace(old,old+'''\n if guestTiming {\n unregister:=timing.ExperimentGuestSource(transfer,func()([]byte,error){\n f,e:=fs.OpenFile("snapshot-out/startup-timing.json",os.O_RDONLY,0);if e!=nil{return nil,e};defer f.Close();return io.ReadAll(f)\n });defer unregister()\n }''')
overlay={};hashes={}
for rel,s in files.items():
 old=(P/rel).read_bytes() if (P/rel).exists() else None
 out=O/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(s);overlay[str(P/rel)]=str(out)
 hashes[rel]=dict(before_sha256=hashlib.sha256(old).hexdigest() if old else None,after_sha256=hashlib.sha256(s.encode()).hexdigest())
(W/'temp/overlay.json').write_text(json.dumps(dict(Replace=overlay),indent=2)+'\n')
(W/'evidence/overlay-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
print('overlay',len(files),'files; same files for both runtime argv values')
