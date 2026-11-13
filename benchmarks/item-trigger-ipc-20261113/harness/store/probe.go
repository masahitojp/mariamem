package store
import("context";"database/sql";"fmt";"os")
const fullInsertTrigger=`CREATE TRIGGER order_items_total_insert AFTER INSERT ON order_items FOR EACH ROW UPDATE orders SET total_cents=(SELECT COALESCE(SUM(quantity*unit_price_cents),0) FROM order_items WHERE order_id=NEW.order_id),updated_at=CURRENT_TIMESTAMP(6) WHERE id=NEW.order_id`
func ConfigureProbe(ctx context.Context,db *sql.DB)error{mode:=os.Getenv("TRIGGER_ARM");if mode=="full"||mode==""{return nil};if mode!="incremental"&&mode!="none"{return fmt.Errorf("invalid trigger arm %q",mode)};if _,e:=db.ExecContext(ctx,"DROP TRIGGER order_items_total_insert");e!=nil{return e};if mode=="incremental"{_,e:=db.ExecContext(ctx,`CREATE TRIGGER order_items_total_insert AFTER INSERT ON order_items FOR EACH ROW UPDATE orders SET total_cents=total_cents+NEW.quantity*NEW.unit_price_cents,updated_at=CURRENT_TIMESTAMP(6) WHERE id=NEW.order_id`);return e};return nil}
var verifyPrefix=os.Getenv("VERIFY_PREFIX")=="1"
func CheckPrefix(ctx context.Context,tx *sql.Tx,id int64)error{if !verifyPrefix{return nil};var got,sum int64;if e:=tx.QueryRowContext(ctx,`SELECT total_cents,(SELECT COALESCE(SUM(quantity*unit_price_cents),0) FROM order_items WHERE order_id=?) FROM orders WHERE id=?`,id,id).Scan(&got,&sum);e!=nil{return e};if os.Getenv("TRIGGER_ARM")=="none"{sum=0};if got!=sum{return fmt.Errorf("prefix total %d != %d",got,sum)};return nil}
func FinishProbe(ctx context.Context,db *sql.DB)error{
 if os.Getenv("ATTRIB_ORACLE")!="1"{return nil}
 mode:=os.Getenv("TRIGGER_ARM")
 if mode=="none"{if _,e:=db.ExecContext(ctx,`UPDATE orders o SET total_cents=(SELECT COALESCE(SUM(i.quantity*i.unit_price_cents),0) FROM order_items i WHERE i.order_id=o.id),updated_at=CURRENT_TIMESTAMP(6)`);e!=nil{return e}}
 if mode=="incremental"||mode=="none"{if _,e:=db.ExecContext(ctx,"DROP TRIGGER IF EXISTS order_items_total_insert");e!=nil{return e};if _,e:=db.ExecContext(ctx,fullInsertTrigger);e!=nil{return e}}
 var orders,items,audits,bad int
 if e:=db.QueryRowContext(ctx,`SELECT (SELECT COUNT(*) FROM orders),(SELECT COUNT(*) FROM order_items),(SELECT COUNT(*) FROM audit_log),(SELECT COUNT(*) FROM orders o WHERE o.total_cents<>(SELECT COALESCE(SUM(i.quantity*i.unit_price_cents),0) FROM order_items i WHERE i.order_id=o.id))`).Scan(&orders,&items,&audits,&bad);e!=nil{return e}
 if orders!=40||items!=100||audits!=40||bad!=0{return fmt.Errorf("end oracle orders=%d items=%d audit=%d bad=%d",orders,items,audits,bad)}
 want:=map[int64]int{};for _,o:=range SampleOrders(){for _,it:=range o.Items{want[it.ProductID]+=it.Quantity}}
 rows,e:=db.QueryContext(ctx,"SELECT id,stock FROM products ORDER BY id");if e!=nil{return e};defer rows.Close();n:=0;for rows.Next(){var id int64;var stock int;if e=rows.Scan(&id,&stock);e!=nil{return e};if stock!=100-want[id]{return fmt.Errorf("stock id%d got%d want%d",id,stock,100-want[id])};n++};if n!=500{return fmt.Errorf("products=%d",n)};return rows.Err()
}
