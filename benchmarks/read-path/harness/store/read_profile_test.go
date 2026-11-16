package store_test
import("context";"testing";"os";"runtime/pprof";"time";"fmt";"github.com/shibukawa/pgmem/bench/modelcase/store")
func TestGetOrderCPUProbe(t *testing.T) {
 db:=fx.shared();if fx.sharedErr!=nil {t.Fatal(fx.sharedErr)}
 f,e:=os.Create(os.Getenv("READ_CPU_PROFILE"));if e!=nil {t.Fatal(e)};defer f.Close()
 if e=pprof.StartCPUProfile(f);e!=nil {t.Fatal(e)}
 start:=time.Now()
 for i:=0;i<4000;i++ {o,e:=store.GetOrder(context.Background(),db,int64(i%40+1));if e!=nil||o.ID!=int64(i%40+1)||len(o.Items)==0 {t.Fatal(o,e)}}
 elapsed:=time.Since(start);pprof.StopCPUProfile();fmt.Printf("GETORDER4000_MS %.3f\n",float64(elapsed)/1e6)
}
