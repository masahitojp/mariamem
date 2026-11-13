package store_test
import("context";"database/sql";"errors";"fmt";"os";"strconv";"sync";"testing";pgmem "github.com/masahitojp/mariamem";"github.com/shibukawa/pgmem/bench/modelcase/store")
func TestAttribution(t *testing.T){if os.Getenv("ATTRIB_ONLY")!="1"{t.Skip("separate sample attribution")};p,e:=strconv.Atoi(os.Getenv("LOAD_PARALLEL"));if e!=nil||p<1||p>8{t.Fatal("bad load parallel")};ctx:=t.Context();for wave:=0;wave<2;wave++{if e:=runAttributionWave(ctx,wave,p);e!=nil{t.Fatal(e)}}}
func runAttributionWave(ctx context.Context,wave,p int)(result error){
 type child struct{server *pgmem.Database;db *sql.DB;ctx context.Context};children:=make([]child,8)
 defer func(){for _,c:=range children{if c.db!=nil{result=errors.Join(result,c.db.Close())};if c.server!=nil{result=errors.Join(result,c.server.Close())}}}()
 phase:=func(fn func(int)error)error{var wg sync.WaitGroup;sem:=make(chan struct{},p);errs:=make(chan error,8);for i:=0;i<8;i++{wg.Add(1);go func(i int){defer wg.Done();sem<-struct{}{};defer func(){<-sem}();if e:=fn(i);e!=nil{errs<-e}}(i)};wg.Wait();close(errs);var e error;for x:=range errs{e=errors.Join(e,x)};return e}
 if e:=phase(func(i int)error{c:=&children[i];c.ctx=context.WithValue(ctx,"mariamem_benchmark_label",fmt.Sprintf("wave%d/child%d",wave,i));var e error;c.server,e=fx.probeSnap.Fork(c.ctx);if e!=nil{return e};c.db=openInProcess(c.server);return nil});e!=nil{return e}
 // No Fork/repair/oracle/Close overlaps any timed LoadSample in this wave.
 if e:=phase(func(i int)error{c:=&children[i];return store.LoadSample(c.ctx,c.db)});e!=nil{return e}
 for _,c:=range children{if e:=store.FinishProbe(c.ctx,c.db);e!=nil{return e}}
 return nil
}
