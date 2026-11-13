from pathlib import Path
import json
r=Path(__file__).resolve().parents[1];src=r/'worktree/internal/generatedgo/image/image.go';s=src.read_text();anchor='f.constructorMS = float64(time.Since(constructorAt)) / 1e6'
assert s.count(anchor)==1
extra='''
 // Experiment only: change the two startup argv literals, preserving lengths.
 // No initialized engine state is copied and no default arm bytes are changed.
 if os.Getenv("MARIAMEM_EXPERIMENT_POOL64")=="1" {
  for _,old:=range []string{"--innodb-buffer-pool-size=16M","--loose-innodb-buffer-pool-size-max=16M"} {
   find:=append([]byte(old),0)
   if bytes.Count(m.Memory[:generated.InitialMemoryBytes],find)!=1 { panic("experiment startup literal missing or duplicated: "+old) }
   replacement:=bytes.Replace(find,[]byte("16M"),[]byte("64M"),1)
   copy(m.Memory[bytes.Index(m.Memory[:generated.InitialMemoryBytes],find):],replacement)
  }
 }
'''
s=s.replace(anchor,anchor+extra);dst=r/'temp/image_overlay.go';dst.write_text(s);(r/'evidence/overlay.json').write_text(json.dumps({'Replace':{str(src):str(dst)}},indent=2))
p=r/'evidence/build.py';s=p.read_text().replace("'test','-c'","'test','-overlay',str(r/'evidence/overlay.json'),'-c'");p.write_text(s)
p=r/'evidence/run.py';s=p.read_text().replace("'cache256','querymem','textparams'","'cache256','querymem','textparams','pool64'").replace("e=env.copy();e.update(","e=env.copy();e['MARIAMEM_EXPERIMENT_POOL64']='1' if arm=='pool64' else '0';e.update(");p.write_text(s)
p=r/'temp/maria/store/fixture_test.go';s=p.read_text().replace('t.Cleanup(func() { db.Close(); s.Close() })','t.Cleanup(func() { if e:=db.Close();e!=nil{t.Error(e)};if e:=s.Close();e!=nil{t.Error(e)} })').replace('snap.Close()\n\t\tsrv.Close()','if e:=snap.Close();e!=nil{panic(e)}\n\t\tif e:=srv.Close();e!=nil{panic(e)}');p.write_text(s)
p=r/'evidence/plan.json';d=json.loads(p.read_text());d['primary_arms'].append('pool64');d['pool64']='Go observation overlay changes two NUL-terminated startup literals 16M->64M before image build, equal length, exactly one occurrence each; verify actual variables and 70 test assertions; no canonical change';p.write_text(json.dumps(d,indent=2))
