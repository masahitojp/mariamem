package store_test
import("context";"database/sql";"errors";"fmt";"os";"strconv";"sync";"testing";pgmem "github.com/masahitojp/mariamem";"github.com/shibukawa/pgmem/bench/modelcase/store")
type probeChild struct{s *pgmem.Database;db *sql.DB;tx *sql.Tx;stmt *sql.Stmt;label string;orders []store.SampleOrder}
func TestInsertOnly(t *testing.T){runProbe(t,true)}
func TestSampleOnly(t *testing.T){runProbe(t,false)}
func runProbe(t *testing.T,raw bool){
 p,e:=strconv.Atoi(os.Getenv("LOAD_PARALLEL"));if e!=nil||p<1||p>8{t.Fatal("bad parallel")};ctx:=t.Context();engine:=os.Getenv("PROBE_ENGINE");children:=make([]probeChild,8);kind:="sample";if raw{kind="raw"}
 defer func(){for _,c:=range children{var err error;if c.stmt!=nil{err=errors.Join(err,c.stmt.Close())};if c.tx!=nil{if e:=c.tx.Rollback();e!=nil&&!errors.Is(e,sql.ErrTxDone){err=errors.Join(err,e)}};if c.db!=nil{err=errors.Join(err,c.db.Close())};if c.s!=nil{err=errors.Join(err,c.s.Close())};if err!=nil{t.Error("close",err)}}}()
 phase:=func(fn func(int)error)error{var wg sync.WaitGroup;sem:=make(chan struct{},p);errs:=make(chan error,8);for i:=0;i<8;i++{wg.Add(1);go func(i int){defer wg.Done();sem<-struct{}{};defer func(){<-sem}();if e:=fn(i);e!=nil{errs<-e}}(i)};wg.Wait();close(errs);var err error;for e:=range errs{err=errors.Join(err,e)};return err}
 if e=phase(func(i int)error{c:=&children[i];c.label=fmt.Sprintf("%s/child%d",kind,i);var e error;c.s,e=fx.probeSnap.Fork(ctx);if e!=nil{return e};c.db=openInProcess(c.s);return nil});e!=nil{t.Fatal(e)}
 if raw{
  if e=phase(func(i int)error{return prepareRaw(ctx,&children[i],engine)});e!=nil{t.Fatal(e)}
  // Only INSERT calls and loop overhead inside each interval. No child's commit overlaps it.
  pgmem.ExperimentPhase(true)
  if e=phase(func(i int)error{c:=&children[i];done:=fx.rec.Start("raw_insert","insert",c.label);err:=insertRaw(ctx,c);done();return err});e!=nil{t.Fatal(e)}
  pgmem.ExperimentPhase(false)
  if e=phase(func(i int)error{c:=&children[i];if e:=c.stmt.Close();e!=nil{return e};c.stmt=nil;err:=c.tx.Commit();c.tx=nil;return err});e!=nil{t.Fatal(e)}
 }else{
  if e=phase(func(i int)error{c:=&children[i];done:=fx.rec.Start("sample_probe","sample",c.label);err:=store.LoadSample(ctx,c.db);done();return err});e!=nil{t.Fatal(e)}
 }
 for i:=range children{t.Run(fmt.Sprintf("child%d",i),func(t *testing.T){checkProbe(t,children[i].db,raw,engine)})}
}
func prepareRaw(ctx context.Context,c *probeChild,engine string)error{
 c.orders=store.SampleOrders();tx,e:=c.db.BeginTx(ctx,nil);if e!=nil{return e};defer tx.Rollback();q:=`INSERT INTO orders(user_id,status) VALUES (?,?) RETURNING id`;if engine=="pg"{q=`INSERT INTO orders(user_id,status) VALUES ($1,$2) RETURNING id`};st,e:=tx.PrepareContext(ctx,q);if e!=nil{return e}
 for _,o:=range c.orders{var id int64;if e=st.QueryRowContext(ctx,o.UserID,o.Status).Scan(&id);e!=nil{st.Close();return e};if id!=o.ID{st.Close();return fmt.Errorf("parent id %d != %d",id,o.ID)}};if e=st.Close();e!=nil{return e};if e=tx.Commit();e!=nil{return e}
 c.tx,e=c.db.BeginTx(ctx,nil);if e!=nil{return e};q=`INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES (?,?,?,?)`;if engine=="pg"{q=`INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES ($1,$2,$3,$4)`};c.stmt,e=c.tx.PrepareContext(ctx,q);return e
}
func insertRaw(ctx context.Context,c *probeChild)error{for _,o:=range c.orders{for _,it:=range o.Items{if _,e:=c.stmt.ExecContext(ctx,o.ID,it.ProductID,it.Quantity,it.UnitPriceCents);e!=nil{return e}}};return nil}
func checkProbe(t *testing.T,db *sql.DB,raw bool,engine string){
 t.Helper();ctx:=t.Context();off:=os.Getenv("TRIGGERS_OFF")=="1";count:=func(q string)int{t.Helper();var n int;if e:=db.QueryRowContext(ctx,q).Scan(&n);e!=nil{t.Fatal(e)};return n}
 wantTriggers:=5;if engine=="pg"{wantTriggers=2};if off{wantTriggers=0};q:=`SELECT count(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE()`;if engine=="pg"{q=`SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal`};if count(q)!=wantTriggers{t.Fatal("user trigger count")}
 audits:=40;if off{audits=0};if count(`SELECT count(*) FROM orders`)!=40||count(`SELECT count(*) FROM order_items`)!=100||count(`SELECT count(*) FROM audit_log`)!=audits{t.Fatal("row counts")}
 q=`SELECT count(*) FROM orders o WHERE o.total_cents<>(SELECT COALESCE(SUM(i.quantity*i.unit_price_cents),0) FROM order_items i WHERE i.order_id=o.id)`;if off{q=`SELECT count(*) FROM orders WHERE total_cents<>0`};if count(q)!=0{t.Fatal("total state")}
 used:=map[int64]int{};if !raw{for _,o:=range store.SampleOrders(){for _,it:=range o.Items{used[it.ProductID]+=it.Quantity}}};rows,e:=db.QueryContext(ctx,`SELECT id,stock FROM products`);if e!=nil{t.Fatal(e)};n:=0;for rows.Next(){var id int64;var stock int;if e=rows.Scan(&id,&stock);e!=nil{t.Fatal(e)};if stock!=100-used[id]{t.Fatal("stock",id)};n++};if e=rows.Err();e!=nil{t.Fatal(e)};rows.Close();if n!=500{t.Fatal("products")}
 for _,bad:=range []string{`INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(999999,1,1,100)`,`INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(1,1,0,100)`}{if _,e=db.ExecContext(ctx,bad);e==nil{t.Fatal("FK/CHECK unexpectedly accepted")}}
 t.Logf("PASS raw=%v off=%v user_triggers=%d orders40/items100/audits%d/totals/500stocks/FK/CHECK",raw,off,wantTriggers,audits)
}
