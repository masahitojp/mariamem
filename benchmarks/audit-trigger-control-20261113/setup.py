from pathlib import Path
import json,hashlib,subprocess,os
r=Path(__file__).resolve().parents[1];pg=r/'temp/pgmem/bench/modelcase/store/seed.go';s=pg.read_text();s=s.replace('"sort"','"sort"\n"os"\n"strings"')
a='\t\tbody, err := migrations.ReadFile("migrations/" + e.Name())';assert a in s
s=s.replace(a,a+'\n        if os.Getenv("AUDIT_ALL_UPDATES")=="1" && e.Name()=="0005_audit.sql" { body=[]byte(strings.Replace(string(body),"AFTER INSERT OR UPDATE OF status ON orders","AFTER INSERT OR UPDATE ON orders",1)) }')
p=r/'temp/pg_seed_overlay.go';p.write_text(s);(r/'evidence/pg-overlay.json').write_text(json.dumps({'Replace':{str(pg):str(p)}},indent=2))
(r/'evidence/pg-seed-overlay.go.txt').write_text(s)
(r/'evidence/plan.json').write_text(json.dumps({'source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','pgmem_source_commit':'a61005d37d01e6671f814fe8ca828222e8147df4','question':'official PG versus same PG with AFTER UPDATE OF status changed to AFTER UPDATE; Maria unchanged reference','primary':'1 warmup each +5 rotated triplets;70 tests each; no IPC observer','arms':['pg-official','pg-all','maria'],'only_pg_schema_delta':'AFTER INSERT OR UPDATE OF status ON orders -> AFTER INSERT OR UPDATE ON orders','limits':'residual is engine+driver+transport+SQL dialect, not isolated engine CPU','budget_gib':10,'min_free_gib':12},indent=2))
