from pathlib import Path
import subprocess,hashlib,json,zipfile,stat
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence';T.mkdir(exist_ok=True);E.mkdir(exist_ok=True)
items=[('build',13598259407,'5248b5e2b8a232bcc8033057df9da184776b14e8c5b59066c56eb36e6dbf1731'),('reference',13597914099,'5785b4ace826613149f1b769a03ca218129ab53234327403d6c0f2f8293e76d6'),('guest',13598059891,'953a2589b5c846ef118c99020a7e6505ff83d0e2d8dc5f617fcdf778467c6f90'),('ubuntu',13597734722,'da2d5a695b8045a924742dbbea1cac87b88e8da218e6e726245d0e9e39fb11ba'),('macos',13598479361,'0d53cbefff2e9aac8e60dfd1426a24cd4b2e0664f337261a160a1c08ad1b8414')]
records=[]
for name,id,h in items:
 p=T/(name+'.zip')
 with p.open('wb') as f:subprocess.run(['gh','api',f'repos/masahitojp/mariamem/actions/artifacts/{id}/zip'],stdout=f,check=True)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==h,name
 target=T/name;target.mkdir()
 with zipfile.ZipFile(p) as z:
  assert sum(x.file_size for x in z.infolist())<1500*1024*1024
  for info in z.infolist():
   q=Path(info.filename);assert not q.is_absolute() and '..' not in q.parts and not stat.S_ISLNK(info.external_attr>>16)
  z.extractall(target)
  print(name,'ZIP digest PASS',len(z.infolist()),z.namelist()[:7],flush=True)
 records.append({'name':name,'artifact':id,'zip_sha256':h,'files':{str(q.relative_to(target)):hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted(target.rglob('*')) if q.is_file()}})
 (E/'artifacts-verified.json').write_text(json.dumps(records,indent=2)+'\n')
for n,api in [('run.json','repos/masahitojp/mariamem/actions/runs/42433100335'),('jobs.json','repos/masahitojp/mariamem/actions/runs/42433100335/jobs?per_page=100'),('artifacts.json','repos/masahitojp/mariamem/actions/runs/42433100335/artifacts')]:
 (E/n).write_bytes(subprocess.check_output(['gh','api',api]))
