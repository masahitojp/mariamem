from pathlib import Path
import re
r=Path(__file__).resolve().parents[1];d=r/'temp/maria/store'
s=(d/'fixture_test.go').read_text().replace('cfg.InterpolateParams=false','cfg.InterpolateParams=os.Getenv("TEXT_PARAMS")=="1"');(d/'fixture_test.go').write_text(s)
s=(d/'store.go').read_text();queries={}
for name in ['RevenueByCategory','GetOrder']:
 body=s[s.index('func '+name+'('):];body=body[:body.index('\n}\n')];qs=re.findall(r'`([^`]+)`',body,re.S)
 for i,q in enumerate(qs):queries[name+str(i)]=q.replace('?', '1')
code='''package store_test
import("testing";"os";"encoding/json")
func TestDiagnostics(t *testing.T){if os.Getenv("DIAGNOSTICS")!="1"{t.Skip("separate diagnostic")};db:=fx.shared();if fx.sharedErr!=nil{t.Fatal(fx.sharedErr)};ctx:=t.Context();out:=map[string]any{};queries:=map[string]string{'''
for k,q in queries.items():code+= '"'+k+'":`'+q+'`,\n'
code+='''};for name,q:=range queries{var plan string;if e:=db.QueryRowContext(ctx,"ANALYZE FORMAT=JSON "+q).Scan(&plan);e!=nil{t.Fatal(e)};out[name]=json.RawMessage(plan)}
 rows,e:=db.QueryContext(ctx,`SHOW GLOBAL STATUS WHERE Variable_name IN ('Innodb_buffer_pool_reads','Innodb_buffer_pool_read_requests','Innodb_buffer_pool_pages_free','Innodb_buffer_pool_wait_free','Innodb_log_waits','Created_tmp_disk_tables','Created_tmp_tables','Opened_tables','Table_open_cache_hits','Table_open_cache_misses','Threads_connected','Max_used_connections')`);if e!=nil{t.Fatal(e)};stats:=map[string]string{};for rows.Next(){var k,v string;if e:=rows.Scan(&k,&v);e!=nil{t.Fatal(e)};stats[k]=v};rows.Close();out["status"]=stats;b,_:=json.MarshalIndent(out,"","  ");if e:=os.WriteFile(os.Getenv("DIAG_PATH"),b,0644);e!=nil{t.Fatal(e)}}
'''
(d/'diagnostics_test.go').write_text(code)
