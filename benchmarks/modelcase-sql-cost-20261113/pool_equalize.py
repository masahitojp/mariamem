from pathlib import Path
r=Path(__file__).resolve().parents[1];p=r/'temp/image_overlay.go';s=p.read_text();a=s.index(' // Experiment only:');b=s.index('\n\tf.globals, f.dataEnd',a)
s=s[:a]+'''
 // Experiment only. Identical bounded literal validation in both arms.
 probeBegin,probeEnd,searchErr:=f.layout.Bounds(uint64(os.Getpagesize()))
 if searchErr!=nil { panic(searchErr) }
 search:=m.Memory[probeBegin:probeEnd]
 for _,old:=range []string{"--innodb-buffer-pool-size=16M","--loose-innodb-buffer-pool-size-max=16M"} {
  find:=append([]byte(old),0)
  if bytes.Count(search,find)!=1 {panic("experiment startup literal missing or duplicated: "+old)}
  if os.Getenv("MARIAMEM_EXPERIMENT_POOL64")=="1" {
   replacement:=bytes.Replace(find,[]byte("16M"),[]byte("64M"),1)
   copy(search[bytes.Index(search,find):],replacement)
  }
 }
'''+s[b:];p.write_text(s)
p=r/'evidence/run_poolfix.py';s=p.read_text().replace('poolfix-','poolequal-').replace("out/'poolfix-runs.json'","out/'poolequal-runs.json'");(r/'evidence/run_poolequal.py').write_text(s)
