from pathlib import Path
import shutil,json,hashlib,subprocess
r=Path(__file__).resolve().parents[1];e=r/'evidence';src=r/'temp/maria';dest=e/'maria-harness'
shutil.copytree(src,dest,ignore=shutil.ignore_patterns('results','bin'),dirs_exist_ok=True)
shutil.copy2(r/'temp/pgmem/LICENSE',dest/'UPSTREAM-LICENSE')
p=e/'build.py';p.write_text(p.read_text().replace("[('maria',r/'temp/maria')]","[('pgmem',r/'temp/pgmem/bench/modelcase'),('maria',r/'temp/maria')]"))
p=e/'prepare.py';p.write_text(p.read_text()+'''\np=dst/'store/fixture_test.go';p.write_text(p.read_text().replace('snap, err := srv.Snapshot(ctx, pgmem.SnapshotOptions{})','if err:=srv.WaitDisconnected(ctx);err!=nil{return err}\\n snap, err := srv.Snapshot(ctx, pgmem.SnapshotOptions{})'))\n''')
info={'mariamem_source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','pgmem_source_commit':'a61005d37d01e6671f814fe8ca828222e8147df4','tag_object_sha':'145e5d2fc70983b89a4bdd8438e547fcd60244ed','host':'Apple M1 / MacBookAir10,1 / 16GiB / 8 logical CPUs / macOS27.2.1 26B131','go':'go1.27.4 darwin/arm64','binary_sha256':{n:hashlib.sha256((r/'temp'/f'{n}.test').read_bytes()).hexdigest() for n in ['maria','pgmem']}}
(e/'inputs.json').write_text(json.dumps(info,indent=2))
for n in ['maria','pgmem']:
 (e/f'{n}-buildinfo.txt').write_text(subprocess.check_output(['go','version','-m',str(r/'temp'/f'{n}.test')],text=True).replace(str(r),'<WORKSPACE>'))
