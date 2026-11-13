from pathlib import Path
import json,shutil
r=Path(__file__).resolve().parents[1];p=r/'temp/maria/store/seed.go';s=(r/'evidence/maria-seed-original.go.txt').read_text();s=s.replace('"sort"','"sort"\n"os"\n"strings"')
a='\t\tbody, err := migrations.ReadFile("migrations/" + e.Name())';assert s.count(a)==1
s=s.replace(a,a+'''\n        if err == nil && os.Getenv("MARIA_AUDIT_OF")=="1" {
          const old = "CREATE TRIGGER orders_audit_update AFTER UPDATE ON orders"
          if strings.Count(string(body),old)!=1 { return fmt.Errorf("expected one audit UPDATE trigger") }
          body=[]byte(strings.Replace(string(body),old,"CREATE TRIGGER orders_audit_update AFTER UPDATE OF status ON orders",1))
        }''')
p.write_text(s);shutil.copyfile(p,r/'evidence/maria-seed.go.txt')
(r/'evidence/plan.json').write_text(json.dumps({'source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','pgmem_source_commit':'a61005d37d01e6671f814fe8ca828222e8147df4','question':'MariaDB AFTER UPDATE OF status versus original AFTER UPDATE; compare with unchanged pgmem official','arms':['pg-official','maria-old','maria-of'],'primary':'1 warmup per arm +5 rotated triplets; same Maria binary;70 tests; observer off','only_delta':'Maria orders_audit_update: AFTER UPDATE ON orders -> AFTER UPDATE OF status ON orders; body unchanged','witness':'independent binary; actual SHOW CREATE; function-entry counter; totals-only/status-first/status-noop; also diagnose status-second separately','limits':'matched firing condition, not pure engine isolation','budget_gib':10,'min_free_gib':12},indent=2))
