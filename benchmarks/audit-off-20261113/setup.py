from pathlib import Path
import shutil,json,difflib
r=Path(__file__).resolve().parents[1];e=r/'evidence'
for engine,d in [('pg',r/'temp/pgmem/bench/modelcase/store'),('maria',r/'temp/maria/store')]:
 for name in ['fixture_test.go','write_test.go']:
  p=d/name;o=e/(engine+'-'+name+'.original.txt')
  if not o.exists():shutil.copyfile(p,o)
  s=o.read_text()
  if name=='fixture_test.go':
   anchor='\treturn nil\n}\n\nfunc version';assert s.count(anchor)==1
   drops=['DROP TRIGGER orders_audit ON orders'] if engine=='pg' else ['DROP TRIGGER orders_audit_insert','DROP TRIGGER orders_audit_update']
   block='\tif os.Getenv("AUDIT_OFF")=="1"{\n'
   for sql in drops:block+=' if _,err:=db.ExecContext(ctx,`'+sql+'`);err!=nil{return fmt.Errorf("drop audit: %w",err)}\n'
   block+=' }\n';s=s.replace(anchor,block+anchor);s+='\nfunc wantAudit(n int)int{if os.Getenv("AUDIT_OFF")=="1"{return 0};return n}\n'
  else:
   assert s.count('if audits != 1 {')==1 and s.count('if audits != 2 {')==1;s=s.replace('if audits != 1 {','if audits != wantAudit(1) {').replace('if audits != 2 {','if audits != wantAudit(2) {')
  p.write_text(s);(e/(engine+'-'+name+'.txt')).write_text(s);(e/(engine+'-'+name+'.patch')).write_text(''.join(difflib.unified_diff(o.read_text().splitlines(True),s.splitlines(True),fromfile=engine+'/'+name+'-original',tofile=engine+'/'+name)))
(e/'plan.json').write_text(json.dumps({'question':'both engines audit INSERT/status UPDATE triggers off; total-recalc triggers remain','source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','pgmem_source_commit':'a61005d37d01e6671f814fe8ca828222e8147df4','baseline':'be114ac4e07b3195d6b5ed0243adb341e220c8b8 normalized modelcase','arms':['pg-on','pg-off','maria-on','maria-off'],'primary':'1 warmup per arm +5 rotated groups;70 scenarios each, audit row expectations zero when off; P8','only_delta':'DROP audit triggers after master preparation before Snapshot; audit table/index remain; do not repair or restore','oracles':'audit trigger absent/present, final counts40/100/0or40, total consistency and stock;70 scenarios','known_issue':'MDEV-42129 not investigated','budget_gib':10,'min_free_gib':12},indent=2))
