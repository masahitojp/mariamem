package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sync/atomic"
	"time"

	"github.com/masahitojp/mariamem"
)

var closeSequence atomic.Uint64
var slowOwner atomic.Uint64

// This observer is harness-only. It changes no database option or shutdown
// deadline and emits nothing for ordinary Close. Diagnostic runs are not timings.
func observeClose(db *mariamem.Database, ctx context.Context) error {
	id := closeSequence.Add(1)
	started := time.Now()
	finished, observed := make(chan struct{}), make(chan struct{})
	go func() {
		defer close(observed)
		thresholds := []time.Duration{2 * time.Second, 10 * time.Second}
		control := os.Getenv("CLOSE_DIAG_CONTROL") == "1"
		if control {
			thresholds[0] = time.Nanosecond
		}
		for index, threshold := range thresholds {
			timer := time.NewTimer(time.Until(started.Add(threshold)))
			select {
			case <-finished:
				timer.Stop()
				return
			case <-timer.C:
			}
			select {
			case <-finished:
				return
			default:
			}
			if slowOwner.Load() != id && !slowOwner.CompareAndSwap(0, id) {
				return
			}
			buffer := make([]byte, 2<<20)
			n := runtime.Stack(buffer, true)
			meta := map[string]any{"close_id": id, "database_pointer": fmt.Sprintf("%p", db),
				"child_index": ctx.Value("forkstages_child"), "elapsed_ms": float64(time.Since(started)) / float64(time.Millisecond),
				"control": control, "stack_bytes": n, "stack_truncated": n == len(buffer), "guest_logs": db.Logs()}
			data, err := json.MarshalIndent(meta, "", "  ")
			if err != nil {
				panic(err)
			}
			prefix := filepath.Join(os.Getenv("CLOSE_DIAG_DIR"), fmt.Sprintf("close-%d-sample-%d", id, index))
			if err = os.WriteFile(prefix+".json", append(data, '\n'), 0600); err != nil {
				panic(err)
			}
			if err = os.WriteFile(prefix+".txt", buffer[:n], 0600); err != nil {
				panic(err)
			}
		}
	}()
	err := db.Close()
	close(finished)
	<-observed
	return err
}
