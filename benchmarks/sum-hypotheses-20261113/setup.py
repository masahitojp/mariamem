from pathlib import Path
import shutil,json,difflib
r=Path(__file__).resolve().parents[1];e=r/'evidence'
for engine,d in [('pg',r/'temp/pgmem/bench/modelcase/store'),('maria',r/'temp/maria/store')]:
 p=d/'seed.go';o=e/(engine+'-seed-original.go.txt')
 if not o.exists():shutil.copyfile(p,o)
 s=o.read_text()
 if engine=='maria':
  anchor='\n\t\tif err != nil {\n\t\t\treturn err\n\t\t}\n\t\ttx := db';assert s.count(anchor)==1
  block='''
        if err==nil {
         mode:=os.Getenv("SUM_EXPERIMENT")
         if mode=="incremental"{
          const old="CREATE TRIGGER order_items_total_insert AFTER INSERT ON order_items FOR EACH ROW UPDATE orders SET total_cents=(SELECT COALESCE(SUM(quantity*unit_price_cents),0) FROM order_items WHERE order_id=NEW.order_id),updated_at=CURRENT_TIMESTAMP(6) WHERE id=NEW.order_id;"
          const next="CREATE TRIGGER order_items_total_insert AFTER INSERT ON order_items FOR EACH ROW UPDATE orders SET total_cents=total_cents+NEW.quantity*NEW.unit_price_cents,updated_at=CURRENT_TIMESTAMP(6) WHERE id=NEW.order_id;"
          if strings.Count(string(body),old)!=1{return fmt.Errorf("incremental anchor missing")};body=[]byte(strings.Replace(string(body),old,next,1))
         }else if mode=="cover"{body=append(body,[]byte("\\nCREATE INDEX idx_order_items_covering ON order_items(order_id,quantity,unit_price_cents);")...)}
        }
'''
 else:
  anchor='\n\t\tif err != nil {\n\t\t\treturn err\n\t\t}\n\t\ttx, err := db.BeginTx';assert s.count(anchor)==1
  block='''
        if err==nil && os.Getenv("SUM_EXPERIMENT")=="incremental" && e.Name()=="0004_totals.sql"{
         const old="BEGIN\\n    UPDATE orders"
         const next="BEGIN\\n    IF TG_OP = 'INSERT' THEN\\n        UPDATE orders SET total_cents=total_cents+NEW.quantity*NEW.unit_price_cents,updated_at=statement_timestamp() WHERE id=NEW.order_id;\\n        RETURN NULL;\\n    END IF;\\n    UPDATE orders"
         if strings.Count(string(body),old)!=1{return fmt.Errorf("incremental anchor missing")};body=[]byte(strings.Replace(string(body),old,next,1))
        }
'''
 s=s.replace(anchor,block+anchor);p.write_text(s);(e/(engine+'-seed.go.txt')).write_text(s);(e/(engine+'-seed.patch')).write_text(''.join(difflib.unified_diff(o.read_text().splitlines(True),s.splitlines(True),fromfile=engine+'-seed-original',tofile=engine+'-seed-switch')))
(e/'plan.json').write_text(json.dumps({'source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','pgmem_source_commit':'a61005d37d01e6671f814fe8ca828222e8147df4','baseline':'be114ac4e07b3195d6b5ed0243adb341e220c8b8 normalized modelcase; audit triggers ON; unmodified70 tests','A':'INSERT total trigger incremental on both; UPDATE/DELETE remain SUM; same statement clock conventions','B':'Maria SUM plus additional (order_id,quantity,unit_price_cents) index, existing indexes retained, no FORCE','arms':['pg-sum','pg-incremental','maria-sum','maria-incremental','maria-cover'],'primary':'1 warmup each +5 cyclically rotated groups of5;70 tests each;P8;no observer','witness':'audits restored; totals/stocks; INSERT prefix + UPDATE/DELETE consistency; actual trigger definitions; covering index and chosen plan','limits':'diagnostic only, no generic SQL rewrite adoption; known MDEV-42129 not investigated','budget_gib':10,'min_free_gib':12},indent=2))
