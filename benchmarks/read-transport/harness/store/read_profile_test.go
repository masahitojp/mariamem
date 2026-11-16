package store_test

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/masahitojp/mariamem"
	"github.com/shibukawa/pgmem/bench/modelcase/store"
	"os"
	"runtime/pprof"
	"testing"
	"time"
)

func TestGetOrderCPUProbe(t *testing.T) {
	db := fx.shared()
	if fx.sharedErr != nil {
		t.Fatal(fx.sharedErr)
	}
	if os.Getenv("TRANSPORT_DIAG") == "1" {
		mariamem.ExperimentTransportBegin()
		defer func() { b, _ := json.Marshal(mariamem.ExperimentTransportEnd()); fmt.Printf("TRANSPORT_STATS %s\n", b) }()
	}
	if p := os.Getenv("READ_CPU_PROFILE"); p != "" {
		f, e := os.Create(p)
		if e != nil {
			t.Fatal(e)
		}
		defer f.Close()
		if e = pprof.StartCPUProfile(f); e != nil {
			t.Fatal(e)
		}
		defer pprof.StopCPUProfile()
	}
	start := time.Now()
	for i := 0; i < 4000; i++ {
		o, e := store.GetOrder(context.Background(), db, int64(i%40+1))
		if e != nil || o.ID != int64(i%40+1) || len(o.Items) == 0 {
			t.Fatal(o, e)
		}
	}
	fmt.Printf("GETORDER4000_MS %.3f\n", float64(time.Since(start))/1e6)
}
