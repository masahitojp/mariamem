package store_test
import("context";"database/sql";"database/sql/driver";"encoding/json";"io";"os";"strings";"sync";"time")
type observation struct {Kind string `json:"kind"`; SQL string `json:"sql"`; MS float64 `json:"ms"`; Rows int `json:"rows"`; Error string `json:"error,omitempty"`}
var om sync.Mutex
var observations []observation
var settings=[]map[string]string{}
func record(kind,q string,t time.Time,rows int,e error){if os.Getenv("OBSERVE")!="1"{return};o:=observation{Kind:kind,SQL:strings.Join(strings.Fields(q)," "),MS:float64(time.Since(t))/1e6,Rows:rows};if e!=nil&&e!=io.EOF{o.Error=e.Error()};om.Lock();observations=append(observations,o);om.Unlock()}
func dumpObservations(){if p:=os.Getenv("OBS_PATH");p!=""{om.Lock();defer om.Unlock();b,_:=json.MarshalIndent(map[string]any{"operations":observations,"settings":settings},"","  ");if e:=os.WriteFile(p,b,0644);e!=nil{panic(e)}}}
type observeConnector struct{driver.Connector}
func(c observeConnector)Connect(ctx context.Context)(driver.Conn,error){x,e:=c.Connector.Connect(ctx);if e!=nil{return nil,e};variant:=os.Getenv("RESOURCE_ARM");var qs []string
switch variant{case "io4":qs=[]string{"SET GLOBAL innodb_read_io_threads=4","SET GLOBAL innodb_write_io_threads=4"};case "cache256":qs=[]string{"SET GLOBAL table_open_cache=256","SET GLOBAL max_connections=32"};case "querymem":qs=[]string{"SET SESSION join_buffer_size=2097152","SET SESSION sort_buffer_size=8388608","SET SESSION tmp_table_size=67108864","SET SESSION max_heap_table_size=67108864"}}
for _,q:=range qs{if _,e=x.(driver.ExecerContext).ExecContext(ctx,q,nil);e!=nil{x.Close();return nil,e}}
return &observedConn{x},nil}
type observedConn struct{driver.Conn}
func(c *observedConn)Prepare(q string)(driver.Stmt,error){return c.PrepareContext(context.Background(),q)}
func(c *observedConn)PrepareContext(ctx context.Context,q string)(driver.Stmt,error){t:=time.Now();s,e:=c.Conn.(driver.ConnPrepareContext).PrepareContext(ctx,q);record("prepare",q,t,0,e);if e!=nil{return nil,e};return &observedStmt{s,q},nil}
func(c *observedConn)ExecContext(ctx context.Context,q string,a []driver.NamedValue)(driver.Result,error){t:=time.Now();r,e:=c.Conn.(driver.ExecerContext).ExecContext(ctx,q,a);record("exec",q,t,0,e);return r,e}
func(c *observedConn)QueryContext(ctx context.Context,q string,a []driver.NamedValue)(driver.Rows,error){t:=time.Now();r,e:=c.Conn.(driver.QueryerContext).QueryContext(ctx,q,a);record("query_return",q,t,0,e);if e!=nil{return nil,e};return &observedRows{Rows:r,q:q,start:t},nil}
func(c *observedConn)BeginTx(ctx context.Context,o driver.TxOptions)(driver.Tx,error){t:=time.Now();x,e:=c.Conn.(driver.ConnBeginTx).BeginTx(ctx,o);record("begin","BEGIN",t,0,e);if e!=nil{return nil,e};return &observedTx{x},nil}
func(c *observedConn)Ping(ctx context.Context)error{return c.Conn.(driver.Pinger).Ping(ctx)}
func(c *observedConn)ResetSession(ctx context.Context)error{if x,ok:=c.Conn.(driver.SessionResetter);ok{return x.ResetSession(ctx)};return nil}
func(c *observedConn)IsValid()bool{if x,ok:=c.Conn.(driver.Validator);ok{return x.IsValid()};return true}
type observedTx struct{driver.Tx}
func(t *observedTx)Commit()error{s:=time.Now();e:=t.Tx.Commit();record("commit","COMMIT",s,0,e);return e}
func(t *observedTx)Rollback()error{return t.Tx.Rollback()}
type observedStmt struct{driver.Stmt;q string}
func(s *observedStmt)ExecContext(ctx context.Context,a []driver.NamedValue)(driver.Result,error){t:=time.Now();r,e:=s.Stmt.(driver.StmtExecContext).ExecContext(ctx,a);record("execute",s.q,t,0,e);return r,e}
func(s *observedStmt)QueryContext(ctx context.Context,a []driver.NamedValue)(driver.Rows,error){t:=time.Now();r,e:=s.Stmt.(driver.StmtQueryContext).QueryContext(ctx,a);record("stmt_query_return",s.q,t,0,e);if e!=nil{return nil,e};return &observedRows{Rows:r,q:s.q,start:t},nil}
type observedRows struct{driver.Rows;q string;start time.Time;n int;done bool}
func(r *observedRows)finish(e error){if !r.done{record("rows_complete",r.q,r.start,r.n,e);r.done=true}}
func(r *observedRows)Next(v []driver.Value)error{e:=r.Rows.Next(v);if e==nil{r.n++}else{r.finish(e)};return e}
func(r *observedRows)Close()error{e:=r.Rows.Close();r.finish(e);return e}
func(r *observedRows)HasNextResultSet()bool{if x,ok:=r.Rows.(driver.RowsNextResultSet);ok{return x.HasNextResultSet()};return false}
func(r *observedRows)NextResultSet()error{if x,ok:=r.Rows.(driver.RowsNextResultSet);ok{return x.NextResultSet()};return io.EOF}
func inspectSettings(ctx context.Context,db *sql.DB)error{
 q:=`SHOW VARIABLES WHERE Variable_name IN ('innodb_buffer_pool_size','innodb_buffer_pool_size_max','innodb_log_buffer_size','innodb_read_io_threads','innodb_write_io_threads','innodb_purge_threads','table_open_cache','max_connections','thread_cache_size','join_buffer_size','sort_buffer_size','tmp_table_size','max_heap_table_size','thread_pool_size','thread_pool_max_threads','innodb_thread_concurrency','optimizer_switch','max_statement_time')`
 rows,e:=db.QueryContext(ctx,q);if e!=nil{return e};defer rows.Close();for rows.Next(){var k,v string;if e:=rows.Scan(&k,&v);e!=nil{return e};settings=append(settings,map[string]string{"name":k,"value":v})};return rows.Err()}
