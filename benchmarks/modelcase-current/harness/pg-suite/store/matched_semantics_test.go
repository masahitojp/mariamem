package store_test
import("context";"fmt";"testing";"os";"reflect";"github.com/shibukawa/pgmem/bench/modelcase/store")
func TestMatchedSemantics(t *testing.T){
 db:=fx.shared();ctx:=context.Background()
 os.Setenv("REVENUE_PREAGG","0");want,err:=store.RevenueByCategory(ctx,db);if err!=nil{t.Fatal(err)}
 os.Setenv("REVENUE_PREAGG","1");got,err:=store.RevenueByCategory(ctx,db);if err!=nil||!reflect.DeepEqual(want,got){t.Fatalf("revenue mismatch %v %v %v",want,got,err)}
 var id int;var status string;if err:=db.QueryRow("SELECT id,status FROM orders ORDER BY id LIMIT 1").Scan(&id,&status);err!=nil{t.Fatal(err)}
 count:=func()int{var n int;if err:=db.QueryRow("SELECT COUNT(*) FROM audit_log").Scan(&n);err!=nil{t.Fatal(err)};return n}
 n:=count();for _,q:=range []string{"UPDATE orders SET total_cents=total_cents WHERE id=", "UPDATE orders SET status=status WHERE id="}{if _,err:=db.Exec(q+fmt.Sprint(id));err!=nil{t.Fatal(err)};if count()!=n{t.Fatal("unexpected audit")}}
 next:="shipped";if status==next{next="paid"};if _,err:=db.Exec("UPDATE orders SET status='"+next+"' WHERE id="+fmt.Sprint(id));err!=nil{t.Fatal(err)};if count()!=n+1{t.Fatal("missing status audit")}
}
