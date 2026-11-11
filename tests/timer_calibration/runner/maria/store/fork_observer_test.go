package store_test

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/masahitojp/mariamem/internal/timing"
	"os"
	"strconv"
	"sync"
)

var forkObs struct {
	sync.Mutex
	Data map[string]map[string]timing.Trace
}

func parallelism() int {
	v, e := strconv.Atoi(os.Getenv("SHOP_PARALLEL"))
	if e != nil || (v != 4 && v != 8) {
		panic("invalid SHOP_PARALLEL")
	}
	return v
}
func observeContext(ctx context.Context, lane string) context.Context {
	if os.Getenv("FORK_STAGES") != "1" {
		return ctx
	}
	return timing.WithRecorder(ctx, func(t timing.Trace) {
		forkObs.Lock()
		defer forkObs.Unlock()
		if forkObs.Data == nil {
			forkObs.Data = map[string]map[string]timing.Trace{}
		}
		if forkObs.Data[lane] == nil {
			forkObs.Data[lane] = map[string]timing.Trace{}
		}
		if _, ok := forkObs.Data[lane][t.Operation]; ok {
			panic(fmt.Sprint("duplicate trace ", lane, " ", t.Operation))
		}
		forkObs.Data[lane][t.Operation] = t
	})
}
func writeForkObservations(path string) error {
	if path == "" {
		return nil
	}
	forkObs.Lock()
	defer forkObs.Unlock()
	b, e := json.Marshal(forkObs.Data)
	if e != nil {
		return e
	}
	return os.WriteFile(path, b, 0644)
}
