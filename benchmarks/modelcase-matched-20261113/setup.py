from pathlib import Path
import json,shutil
r=Path(__file__).resolve().parents[1];e=r/'evidence';m=r/'temp/maria/store';pg=r/'temp/pgmem/bench/modelcase/store'
def original(p,name):
 q=e/name
 if not q.exists():shutil.copyfile(p,q)
 return q.read_text()
s=original(m/'seed.go','maria-seed-original.go.txt');anchor='\n\t\tif err != nil {\n\t\t\treturn err\n\t\t}\n\t\ttx := db';assert s.count(anchor)==1
block='''
        if err==nil && os.Getenv("MODELCASE_MATCHED")=="1" {
         edits:=[][2]string{
          {"old_status VARCHAR(20),new_status VARCHAR(20) NOT NULL", "old_status ENUM('pending','paid','shipped','cancelled'),new_status ENUM('pending','paid','shipped','cancelled') NOT NULL"},
          {"CREATE INDEX products_name_lower ON products(name);", "ALTER TABLE products ADD COLUMN name_lower VARCHAR(255) AS (lower(name)) VIRTUAL; CREATE INDEX products_name_lower ON products(name_lower);"},
          {"FOR EACH ROW INSERT INTO audit_log(order_id,old_status,new_status) SELECT NEW.id,OLD.status,NEW.status WHERE NOT(NEW.status <=> OLD.status);", "FOR EACH ROW BEGIN IF NOT(NEW.status <=> OLD.status) THEN INSERT INTO audit_log(order_id,old_status,new_status) VALUES(NEW.id,OLD.status,NEW.status); END IF; END;"},
         }
         for _,edit:=range edits{if strings.Count(string(body),edit[0])!=1{return fmt.Errorf("missing matched schema anchor %s",edit[0])};body=[]byte(strings.Replace(string(body),edit[0],edit[1],1))}
        }
'''
s=s.replace(anchor,block+anchor);(m/'seed.go').write_text(s)
s=original(m/'store.go','maria-store-original.go.txt');s=s.replace('"fmt"','"fmt"\n"os"') if '"fmt"' in s else s.replace('import (','import (\n"os"');a='func SearchProducts(ctx context.Context, db DB, prefix string) ([]Product, error) {\n\trows, err := db.QueryContext(ctx, `';assert a in s;s=s.replace(a,'func SearchProducts(ctx context.Context, db DB, prefix string) ([]Product, error) {\n field:="lower(name)";if os.Getenv("MODELCASE_MATCHED")=="1"{field="name_lower"}\n\trows, err := db.QueryContext(ctx, `');s=s.replace('WHERE lower(name) LIKE CONCAT(lower(?),', 'WHERE `+field+` LIKE CONCAT(lower(?),');(m/'store.go').write_text(s)
s=original(pg/'seed.go','pg-seed-original.go.txt');s=s.replace('"sort"','"sort"\n"os"\n"strings"');a='\t\tbody, err := migrations.ReadFile("migrations/" + e.Name())';assert a in s;s=s.replace(a,a+'\n if err==nil && os.Getenv("MODELCASE_MATCHED")=="1"{body=[]byte(strings.ReplaceAll(string(body),"now()","statement_timestamp()"))}');(pg/'seed.go').write_text(s)
s=original(pg/'fixture_test.go','pg-fixture-original.go.txt');a='\tdone()\n\n\tf.isolated = func(t *testing.T) *sql.DB {';assert s.count(a)==1
s=s.replace(a,'''\tdone()
 if os.Getenv("MODELCASE_MATCHED")=="1"{
  done=f.rec.Start("snapshot_source_close","close","setup");if err:=srv.Close();err!=nil{return err};done()
  done=f.rec.Start("reader_fork","fork","setup");srv,err=snap.Fork(ctx);if err!=nil{return err};done()
 }

 f.isolated = func(t *testing.T) *sql.DB {''');(pg/'fixture_test.go').write_text(s)
for n,p in [('maria-seed',m/'seed.go'),('maria-store',m/'store.go'),('pg-seed',pg/'seed.go'),('pg-fixture',pg/'fixture_test.go')]:shutil.copyfile(p,e/(n+'.go.txt'))
(e/'plan.json').write_text(json.dumps({'question':'align low-risk harness SQL and reader lifecycle using existing APIs','arms':['pg-official','pg-matched','maria-of','maria-matched'],'source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','pgmem_source_commit':'a61005d37d01e6671f814fe8ca828222e8147df4','changes':['PG reader from new Fork, close restarted original before reader Fork; time recorded','PG application timestamps now -> statement_timestamp','Maria audit status varchar -> enum same labels','Maria audit condition INSERT SELECT -> IF then INSERT VALUES','Maria lower(name) generated virtual column index and query uses indexed column'],'primary':'1 warmup/arm +5 rotated groups of4;70 tests each;P8;observer off','limits':'not pure engine comparison; text/collation/default resources/transport/Snapshot internals remain; known UPDATE OF bug not investigated','budget_gib':10,'min_free_gib':12},indent=2))
