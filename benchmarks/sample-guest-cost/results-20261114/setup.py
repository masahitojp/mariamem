from pathlib import Path
import shutil,json,re
W=Path.cwd()/'build/experiment-work/sample-guest-study';E=W/'evidence';T=W/'temp'
old=Path('build/experiment-work/pgmem-after-buffer/evidence/original-harness')
for name in ['maria-suite','pg-suite']:
 shutil.copytree(old/name,T/name)
 p=T/name/'go.mod';s=p.read_text();s=re.sub(r'replace github.com/masahitojp/mariamem => .*',f'replace github.com/masahitojp/mariamem => {W}/worktree',s);s=re.sub(r'\nreplace github.com/shibukawa/pgmem => .*','',s);p.write_text(s)
 src=T/name/'store/store.go';s=src.read_text();a=s.index('`',s.index('func RevenueByCategory'));b=s.index('`',a+1);orig=s[a+1:b]
 alt="""SELECT c.name, COALESCE(s.cents, 0)
 FROM categories c LEFT JOIN (
 SELECT p.category_id, SUM(i.quantity * i.unit_price_cents) AS cents
 FROM order_items i JOIN orders o ON o.id=i.order_id AND o.status IN ('paid','shipped')
 JOIN products p ON p.id=i.product_id GROUP BY p.category_id
 ) s ON s.category_id=c.id ORDER BY 2 DESC, c.name"""
 s=s[:a]+'revenueSQL()'+s[b+1:];s=s.replace('"context"','"context"\n "os"') if '"os"' not in s else s;s+='\nfunc revenueSQL() string { if os.Getenv("REVENUE_PREAGG")=="1" {return `'+alt+'`};return `'+orig+'`}\n';src.write_text(s)
 (T/name/'store/revenue_probe_test.go').write_text('''package store_test
import("context";"testing";"fmt";"encoding/json";"os";"reflect";"time";"github.com/shibukawa/pgmem/bench/modelcase/store")
func TestRevenueProbe(t *testing.T){
 db:=fx.shared();ctx:=context.Background();os.Setenv("REVENUE_PREAGG","0");want,err:=store.RevenueByCategory(ctx,db);if err!=nil{t.Fatal(err)}
 os.Setenv("REVENUE_PREAGG","1");got,err:=store.RevenueByCategory(ctx,db);if err!=nil||!reflect.DeepEqual(want,got){t.Fatalf("mismatch %v %v %v",want,got,err)}
 var results [][2]float64
 for i:=0;i<100;i++ {var pair [2]float64;for j:=0;j<2;j++{arm:=(i+j)%2;os.Setenv("REVENUE_PREAGG",fmt.Sprint(arm));at:=time.Now();got,err=store.RevenueByCategory(ctx,db);if err!=nil||!reflect.DeepEqual(want,got){t.Fatal("oracle",err)};pair[arm]=float64(time.Since(at).Nanoseconds())/1e6};results=append(results,pair)}
 b,_:=json.Marshal(results);fmt.Println("REVENUE_PAIRS",string(b))
}
''')
 # record explain SQL as a separate test, both definitions copied exactly
 explain='ANALYZE FORMAT=JSON ' if name=='maria-suite' else 'EXPLAIN (ANALYZE, FORMAT JSON) '
 with (T/name/'store/revenue_probe_test.go').open('a') as f:
  f.write('func TestRevenuePlans(t *testing.T){db:=fx.shared();ctx:=context.Background();for arm,q:=range []string{`'+orig+'`,`'+alt+'`}{rows,err:=db.QueryContext(ctx,`'+explain+'`+q);if err!=nil{t.Fatal(err)};for rows.Next(){var s string;if err:=rows.Scan(&s);err!=nil{t.Fatal(err)};fmt.Printf("PLAN %d %s\\n",arm,s)};if err:=rows.Err();err!=nil{t.Fatal(err)};rows.Close()}}\n')
 if name=='maria-suite':
  f=T/name/'store/fixture_test.go';s=f.read_text().replace('if err := store.LoadSample(ctx, db); err != nil {','if err := loadUnlessProbe(ctx, db); err != nil {');f.write_text(s)
  (T/name/'store/sample_probe_test.go').write_text('''package store_test
import("context";"database/sql";"testing";"os";"runtime/pprof";"github.com/shibukawa/pgmem/bench/modelcase/store")
func loadUnlessProbe(ctx context.Context,db *sql.DB)error{if os.Getenv("SAMPLE_PROFILE")=="1"{return nil};return store.LoadSample(ctx,db)}
func TestSampleProfile(t *testing.T){if os.Getenv("SAMPLE_PROFILE")!="1"{t.Skip()};for i:=0;i<64;i++{t.Run("load",func(t *testing.T){db:=fx.isolated(t);pprof.Do(context.Background(),pprof.Labels("operation","sample"),func(ctx context.Context){if err:=store.LoadSample(ctx,db);err!=nil{t.Fatal(err)}});var n int;if err:=db.QueryRow("SELECT COUNT(*) FROM order_items").Scan(&n);err!=nil||n!=100{t.Fatalf("count %d %v",n,err)}})}}
''')
shutil.copy('/private/tmp/setup182.py',E/'setup.py')
(E/'plan.json').write_text(json.dumps({'source_commit':'bb1e937ae75b5788c8548a52987d9d42f78292d5','profile':'64 sequential fresh children, pprof operation=sample label; forks excluded by label filter','sql':'100 alternating paired queries x3 processes per engine; plans and result equality','suite':'P1/P8, 3 pairs per engine if probe supports candidate; original kept','budget_gib':12,'min_free_gib':8,'build_timeout_s':1200,'measurement_timeout_s':180,'scope':'investigation only'},indent=2))
