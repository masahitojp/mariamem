from pathlib import Path
import subprocess,shutil,json
r=Path(__file__).resolve().parents[1];dst=r/'temp/maria';dst.mkdir(parents=True,exist_ok=True)
prefix='benchmarks/pgmem-modelcase-20261113/maria-harness/'
files=subprocess.check_output(['git','ls-tree','-r','--name-only','experiment/pgmem-modelcase',prefix],text=True).splitlines()
for f in files:
 p=dst/f[len(prefix):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(subprocess.check_output(['git','show','experiment/pgmem-modelcase:'+f]))
# Change only measurement harness, not product.
p=dst/'store/fixture_test.go';s=p.read_text().replace('c,err:=mysql.NewConnector(cfg);if err!=nil{panic(err)};return sql.OpenDB(c)','c,err:=mysql.NewConnector(cfg);if err!=nil{panic(err)};return sql.OpenDB(observeConnector{c})')
s=s.replace('code := m.Run()','code := m.Run()\n dumpObservations()');s=s.replace('db := openInProcess(srv)\n\tif err := prepare','db := openInProcess(srv)\n if err:=inspectSettings(ctx,db);err!=nil{return err}\n\tif err := prepare');p.write_text(s)
print(dst)
