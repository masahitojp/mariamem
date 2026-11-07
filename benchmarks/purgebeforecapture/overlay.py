from pathlib import Path
import runpy,sys,json,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);d=s/'benchmarks/purgebeforecapture'
runpy.run_path(str(s/'benchmarks/trxstartupsplit/overlay.py'),run_name='__main__')
m=json.loads((o/'overlay.json').read_text());h=json.loads((o/'hashes.json').read_text());p=s/'benchmarks/staticimageruntime/probe/probe.go';inp=Path(m['Replace'].get(str(p),p));old=inp.read_text();v=old
for before,after in [
 ('type Report struct {','type Report struct {\n PurgeMode string `json:"purge_mode"`\n Purge PurgeReport `json:"purge"`'),
 ('\t\tif err = measured(&r.Root, r.origin, "root_retire",','\t\tif err = measured(&r.Root,r.origin,"purge_before_capture",func()error{return purgeBeforeCapture(ctx,c,r)});err!=nil{return}\n\t\tif err = measured(&r.Root, r.origin, "root_retire",'),
 ('\tflag.Parse()','\tflag.StringVar(&r.PurgeMode,"purge-mode","now","now or bounded drain before snapshot")\n\tflag.Parse()')]:
 assert v.count(before)==1,before;v=v.replace(before,after)
out=o/'purgewait-probe.go';out.write_text(v);m['Replace'][str(p)]=str(out);h.append({'path':str(p.relative_to(s)),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(v.encode()).hexdigest()})
for src,dst in [('wait.go.txt','purge_wait.go'),('wait-test.go.txt','purge_wait_test.go')]:
 p=s/'benchmarks/staticimageruntime/probe'/dst;inp=d/src;m['Replace'][str(p)]=str(inp);h.append({'path':str(p.relative_to(s)),'before_sha256':None,'after_sha256':hashlib.sha256(inp.read_bytes()).hexdigest()})
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n');(o/'hashes.json').write_text(json.dumps(h,indent=2)+'\n')
