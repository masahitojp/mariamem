package store_test
import("context";"testing";"fmt";"encoding/json";"os";"reflect";"time";"github.com/shibukawa/pgmem/bench/modelcase/store")
func TestRevenueProbe(t *testing.T){
 db:=fx.shared();ctx:=context.Background();os.Setenv("REVENUE_PREAGG","0");want,err:=store.RevenueByCategory(ctx,db);if err!=nil{t.Fatal(err)}
 os.Setenv("REVENUE_PREAGG","1");got,err:=store.RevenueByCategory(ctx,db);if err!=nil||!reflect.DeepEqual(want,got){t.Fatalf("mismatch %v %v %v",want,got,err)}
 var results [][2]float64
 for i:=0;i<100;i++ {var pair [2]float64;for j:=0;j<2;j++{arm:=(i+j)%2;os.Setenv("REVENUE_PREAGG",fmt.Sprint(arm));at:=time.Now();got,err=store.RevenueByCategory(ctx,db);if err!=nil||!reflect.DeepEqual(want,got){t.Fatal("oracle",err)};pair[arm]=float64(time.Since(at).Nanoseconds())/1e6};results=append(results,pair)}
 b,_:=json.Marshal(results);fmt.Println("REVENUE_PAIRS",string(b))
}
func TestRevenuePlans(t *testing.T){db:=fx.shared();ctx:=context.Background();for arm,q:=range []string{`
		SELECT c.name, COALESCE(sum(s.cents), 0)
		  FROM categories c
		  LEFT JOIN (
		        SELECT p.category_id, i.quantity * i.unit_price_cents AS cents
		          FROM order_items i
		          JOIN orders o ON o.id = i.order_id AND o.status IN ('paid', 'shipped')
		          JOIN products p ON p.id = i.product_id
		       ) s ON s.category_id = c.id
		 GROUP BY c.id, c.name
		 ORDER BY 2 DESC, c.name`,`SELECT c.name, COALESCE(s.cents, 0)
 FROM categories c LEFT JOIN (
 SELECT p.category_id, SUM(i.quantity * i.unit_price_cents) AS cents
 FROM order_items i JOIN orders o ON o.id=i.order_id AND o.status IN ('paid','shipped')
 JOIN products p ON p.id=i.product_id GROUP BY p.category_id
 ) s ON s.category_id=c.id ORDER BY 2 DESC, c.name`}{rows,err:=db.QueryContext(ctx,`ANALYZE FORMAT=JSON `+q);if err!=nil{t.Fatal(err)};for rows.Next(){var s string;if err:=rows.Scan(&s);err!=nil{t.Fatal(err)};fmt.Printf("PLAN %d %s\n",arm,s)};if err:=rows.Err();err!=nil{t.Fatal(err)};rows.Close()}}
