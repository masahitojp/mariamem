from pathlib import Path
import hashlib,json,runpy,sys
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);d=s/'benchmarks/crcfresh'
runpy.run_path(str(s/'benchmarks/crcfast/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text())
def patch(rel,edits,name):
 p=s/rel;before=Path(m['Replace'].get(str(p),p)).read_text();after=before
 for a,b in edits:
  assert after.count(a)==1,(rel,a,after.count(a));after=after.replace(a,b)
 out=o/name;out.write_text(after);m['Replace'][str(p)]=str(out);h.append(dict(path=rel,before_sha256=hashlib.sha256(before.encode()).hexdigest(),after_sha256=hashlib.sha256(after.encode()).hexdigest()))
patch('internal/generatedgo/code/p4/p4_pure.go',[
 ('func Fn18145(m *base.Module, l0 int32, l1 int32, l2 int32) int32 {','func Fn18145(m *base.Module, l0 int32, l1 int32, l2 int32) int32 {\n base.CRCProbeEnter(m)'),
 ('vc.CRCBegin(v40)\n if base.CRCFastEnabled','vc.CRCBegin(v40)\n base.CRCProbeRecord(m,v40)\n if base.CRCFastEnabled')], 'crc-count-p4.go')
patch('internal/generatedgo/code/base/update_notify.go',[('type uwState struct {','type uwState struct {\n CRC CRCProbeCounters `json:"crc"`')],'crc-owner.go')
patch('benchmarks/staticimageruntime/probe/probe.go',[
 ('type Report struct {','type Report struct {\n CRC map[string]uint64 `json:"crc"`'),
 ('var CleanupStats func()', 'var CRCStats func()map[string]uint64\nvar CleanupStats func()'),
 ('r.MaxRSS = after.Maxrss','r.MaxRSS = after.Maxrss\n if CRCStats!=nil{r.CRC=CRCStats()}')],'crc-probe.go')
patch('benchmarks/staticimageruntime/maria/main.go',[('func main() {','func main() {\n probe.CRCStats=base.CRCProbeStats')],'crc-main.go')
for src,dst in [('counter.go.txt','crc_probe.go'),('counter-test.go.txt','crc_probe_test.go')]:
 p=s/'internal/generatedgo/code/base'/dst;inp=d/src;m['Replace'][str(p)]=str(inp);h.append(dict(path=str(p.relative_to(s)),before_sha256=None,after_sha256=hashlib.sha256(inp.read_bytes()).hexdigest()))
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n')
(o/'counter-mapping.json').write_text(json.dumps(dict(entry='Fn18145 entry; all validator calls',crc='L23 before CRCFastEnabled branch; all selected full-page CRC compute paths',scope='atomic process lifetime total and mutex-protected exact ThreadPool child owner lifetime; root/unbound = total minus child sums',mode='process result records actual CRCFastEnabled',timing='counts only, no per-call timers; process stats captured after suite timer and resource sample'),indent=2)+'\n')
