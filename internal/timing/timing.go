// Package timing provides opt-in benchmark diagnostics, outside runtime protocols.
package timing

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"sync/atomic"
	"time"
)

var sequence atomic.Uint64

type key struct{}
type Event struct {
	Name   string `json:"name"`
	Offset int64  `json:"offset_ns"`
}
type Trace struct {
	Operation string  `json:"operation"`
	PID       int     `json:"pid"`
	Events    []Event `json:"events"`
	start     time.Time
	dir       string
}

// Begin is disabled unless the benchmark explicitly supplies a trace directory.
func Begin(ctx context.Context, operation string) (context.Context, func()) {
	dir := os.Getenv("MARIAMEM_TIMING_DIR")
	if dir == "" {
		return ctx, func() {}
	}
	t := &Trace{Operation: operation, PID: os.Getpid(), start: time.Now(), dir: dir}
	ctx = context.WithValue(ctx, key{}, t)
	Mark(ctx, "begin")
	return ctx, func() {
		Mark(ctx, "end")
		data, err := json.Marshal(t)
		if err != nil {
			return
		}
		// Diagnostics never change the result of a lifecycle operation. The benchmark
		// checks for absent records. Unique names also support multiple Go instances.
		_ = os.WriteFile(filepath.Join(dir, strconv.Itoa(t.PID)+"-"+operation+"-"+strconv.FormatUint(sequence.Add(1), 10)+".json"), data, 0600)
	}
}
func Mark(ctx context.Context, name string) {
	if t, ok := ctx.Value(key{}).(*Trace); ok {
		t.Events = append(t.Events, Event{Name: name, Offset: time.Since(t.start).Nanoseconds()})
	}
}
