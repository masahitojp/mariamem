package store_test
import("context";"database/sql";"errors";"fmt";"net";"net/url";"os";"sync";"github.com/go-sql-driver/mysql";gmclient "github.com/go-mysql-org/go-mysql/client";gmdriver "github.com/go-mysql-org/go-mysql/driver";gmmysql "github.com/go-mysql-org/go-mysql/mysql")
var dialRoutes sync.Map
func commonOption(c *gmclient.Conn)error{c.SetCapability(gmmysql.CLIENT_FOUND_ROWS|gmmysql.CLIENT_MULTI_STATEMENTS);return c.SetCollation("utf8mb4_general_ci")}
func init(){
 gmdriver.ExperimentDialer=func(ctx context.Context,network,addr string)(net.Conn,error){v,ok:=dialRoutes.Load(addr);if !ok{return nil,fmt.Errorf("missing benchmark dial route")};return v.(func(context.Context,string,string)(net.Conn,error))(ctx,network,addr)}
 gmdriver.SetDSNOptions(map[string]gmdriver.DriverOption{"benchmarkCaps":func(c *gmclient.Conn,_ string)error{return commonOption(c)}})
}
func prepareClient(ctx context.Context,c *probeChild)error{
 if err:=c.db.Close();err!=nil{return err};c.db=nil
 cfg,err:=mysql.ParseDSN(c.s.DSN());if err!=nil{return err};path:=os.Getenv("MYSQL_CLIENT_PATH");addr:=cfg.Addr;dialRoutes.Store(addr,c.s.DialContext)
 const query=`INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES (?,?,?,?)`
 if path=="native"{
  conn,err:=gmclient.ConnectWithDialer(ctx,"tcp",addr,cfg.User,cfg.Passwd,cfg.DBName,c.s.DialContext,commonOption);if err!=nil{return err}
  committed:=false;var st *gmclient.Stmt
  c.clientCleanup=func()error{var e error;if st!=nil{e=errors.Join(e,st.Close());st=nil};if !committed{e=errors.Join(e,conn.Rollback())};e=errors.Join(e,conn.Close());dialRoutes.Delete(addr);return e}
  // Session info is outside measured INSERT interval.
  info,e:=conn.Execute(`SELECT @@character_set_client,@@collation_connection,@@autocommit`);if e!=nil{return e};var parts []string;for i:=0;i<3;i++{v,e:=info.GetString(0,i);if e!=nil{info.Close();return e};parts=append(parts,v)};c.session=fmt.Sprint(parts);info.Close()
  if err=conn.Begin();err!=nil{return err};st,err=conn.Prepare(query);if err!=nil{return err}
  c.rawExec=func(id,pid,qty,price int64)error{r,e:=st.Execute(id,pid,qty,price);if e!=nil{return e};n:=r.AffectedRows;r.Close();if n!=1{return fmt.Errorf("affected rows %d",n)};return nil}
  c.rawFinish=func()error{if e:=st.Close();e!=nil{return e};st=nil;if e:=conn.Commit();e!=nil{return e};committed=true;if e:=c.clientCleanup();e!=nil{return e};c.clientCleanup=nil;c.db=openInProcess(c.s);return nil};return nil
 }
 var db *sql.DB
 if path=="stdlib"{db=sql.OpenDB(gmdriver.Connector{Addr:addr,User:cfg.User,Password:cfg.Passwd,DB:cfg.DBName,Params:url.Values{"benchmarkCaps":{"1"},"retries":{"off"}}})}else if path=="standard"{db=openInProcess(c.s)}else{return fmt.Errorf("unknown client path %q",path)}
 c.db=db;db.SetMaxOpenConns(1);var a,b,z string;if err=db.QueryRowContext(ctx,`SELECT @@character_set_client,@@collation_connection,@@autocommit`).Scan(&a,&b,&z);err!=nil{return err};c.session=fmt.Sprint([]string{a,b,z})
 c.tx,err=db.BeginTx(ctx,nil);if err!=nil{return err};c.stmt,err=c.tx.PrepareContext(ctx,query);if err!=nil{return err}
 c.rawExec=func(id,pid,qty,price int64)error{r,e:=c.stmt.ExecContext(ctx,id,pid,qty,price);if e!=nil{return e};n,e:=r.RowsAffected();if e!=nil{return e};if n!=1{return fmt.Errorf("affected rows %d",n)};return nil}
 c.rawFinish=func()error{if e:=c.stmt.Close();e!=nil{return e};c.stmt=nil;if e:=c.tx.Commit();e!=nil{return e};c.tx=nil;if e:=c.db.Close();e!=nil{return e};dialRoutes.Delete(addr);c.db=openInProcess(c.s);return nil};return nil
}
