from pathlib import Path
import shutil,difflib,json
r=Path(__file__).resolve().parents[1];e=r/'evidence'
for engine,d,server in [('pg',r/'temp/pgmem/bench/modelcase/store','Server'),('maria',r/'temp/maria/store','Database')]:
 p=d/'fixture_test.go';o=e/(engine+'-fixture-original.go.txt')
 if not o.exists():shutil.copyfile(p,o)
 s=o.read_text().replace('type fixture struct {','type fixture struct {\n probeSnap *pgmem.Snapshot',1);a='f.isolated = func(t *testing.T) *sql.DB {';assert s.count(a)==2;s=s.replace(a,'f.probeSnap=snap\n '+a,1)
 anchor='\treturn nil\n}\n\nfunc version';assert s.count(anchor)==1
 drops=['DROP TRIGGER orders_audit ON orders','DROP TRIGGER order_items_total ON order_items'] if engine=='pg' else ['DROP TRIGGER orders_audit_insert','DROP TRIGGER orders_audit_update','DROP TRIGGER order_items_total_insert','DROP TRIGGER order_items_total_update','DROP TRIGGER order_items_total_delete']
 block='\tif os.Getenv("TRIGGERS_OFF")=="1"{\n'
 for sql in drops:block+='if _,err:=db.ExecContext(ctx,`'+sql+'`);err!=nil{return fmt.Errorf("drop trigger: %w",err)}\n'
 block+='}\n';s=s.replace(anchor,block+anchor);p.write_text(s);(e/(engine+'-fixture.go.txt')).write_text(s);(e/(engine+'-fixture.patch')).write_text(''.join(difflib.unified_diff(o.read_text().splitlines(True),s.splitlines(True),fromfile=engine+'-original',tofile=engine+'-fixture')))
 probe=(e/'probe_test.go.txt').read_text().replace('SERVER',server).replace('PGIMPORT','github.com/shibukawa/pgmem' if engine=='pg' else 'github.com/masahitojp/mariamem');(d/'insert_probe_test.go').write_text(probe)
(e/'plan.json').write_text(json.dumps({'source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','pgmem_source_commit':'a61005d37d01e6671f814fe8ca828222e8147df4','baseline':'be114ac4e07b3195d6b5ed0243adb341e220c8b8 normalized modelcase, full SUM/audit','off':'all USER triggers dropped before Snapshot; FK/CHECK/indexes retained','workloads':['raw100 detail INSERTs, parents/preparation/commit outside timing','unmodified LoadSample40orders/100items/100stock updates incl commit'],'design':'8 fresh child DBs/workload/process; all Forks/preparation finish before timed operations; all timed raw loops finish before any commits; all loads finish before oracles/Close','primary':'P1/P8;4 on/off arms;1 warmup+5 rotated repeats each =48 processes,16 checked child DBs/process','limits':'dedicated probes, not original70-test suite wall; no repair/restoration; timestamps/driver/default-resource differences remain','budget_gib':10,'min_free_gib':12},indent=2))
