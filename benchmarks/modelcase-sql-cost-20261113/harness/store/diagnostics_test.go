package store_test
import("testing";"os";"encoding/json")
func TestDiagnostics(t *testing.T){if os.Getenv("DIAGNOSTICS")!="1"{t.Skip("separate diagnostic")};db:=fx.shared();if fx.sharedErr!=nil{t.Fatal(fx.sharedErr)};ctx:=t.Context();out:=map[string]any{};queries:=map[string]string{"RevenueByCategory0":`
		SELECT c.name, COALESCE(sum(s.cents), 0)
		  FROM categories c
		  LEFT JOIN (
		        SELECT p.category_id, i.quantity * i.unit_price_cents AS cents
		          FROM order_items i
		          JOIN orders o ON o.id = i.order_id AND o.status IN ('paid', 'shipped')
		          JOIN products p ON p.id = i.product_id
		       ) s ON s.category_id = c.id
		 GROUP BY c.id, c.name
		 ORDER BY 2 DESC, c.name`,
"GetOrder0":`SELECT user_id, status, total_cents FROM orders WHERE id = 1`,
"GetOrder1":`SELECT product_id, quantity, unit_price_cents FROM order_items WHERE order_id = 1 ORDER BY id`,
};for name,q:=range queries{var plan string;if e:=db.QueryRowContext(ctx,"ANALYZE FORMAT=JSON "+q).Scan(&plan);e!=nil{t.Fatal(e)};out[name]=json.RawMessage(plan)}
 rows,e:=db.QueryContext(ctx,`SHOW GLOBAL STATUS WHERE Variable_name IN ('Innodb_buffer_pool_reads','Innodb_buffer_pool_read_requests','Innodb_buffer_pool_pages_free','Innodb_buffer_pool_wait_free','Innodb_log_waits','Created_tmp_disk_tables','Created_tmp_tables','Opened_tables','Table_open_cache_hits','Table_open_cache_misses','Threads_connected','Max_used_connections')`);if e!=nil{t.Fatal(e)};stats:=map[string]string{};for rows.Next(){var k,v string;if e:=rows.Scan(&k,&v);e!=nil{t.Fatal(e)};stats[k]=v};rows.Close();out["status"]=stats;b,_:=json.MarshalIndent(out,"","  ");if e:=os.WriteFile(os.Getenv("DIAG_PATH"),b,0644);e!=nil{t.Fatal(e)}}
