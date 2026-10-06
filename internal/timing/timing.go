// Package timing provides opt-in benchmark diagnostics, without changing runtime protocols.
package timing

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

var sequence atomic.Uint64

type key struct{}
type recorderKey struct{}

// WithRecorder associates benchmark traces with concurrent public API calls.
// Recording remains opt-in through MARIAMEM_TIMING_DIR; it changes no public API.
func WithRecorder(ctx context.Context, record func(Trace)) context.Context {
	return context.WithValue(ctx, recorderKey{}, record)
}

type Event struct {
	Name         string `json:"name"`
	Offset       int64  `json:"offset_ns"`
	BytesRead    int64  `json:"bytes_read,omitempty"`
	FilesTouched int64  `json:"files_touched,omitempty"`
}
type Trace struct {
	mu         *sync.Mutex
	Operation  string          `json:"operation"`
	PID        int             `json:"pid"`
	RuntimePID int             `json:"runtime_pid,omitempty"`
	Events     []Event         `json:"events"`
	Guest      json.RawMessage `json:"guest,omitempty"`
	start      time.Time
	dir        string
}

// Begin is disabled unless the benchmark explicitly supplies a trace directory.
func Begin(ctx context.Context, operation string) (context.Context, func()) {
	dir := os.Getenv("MARIAMEM_TIMING_DIR")
	if dir == "" {
		return ctx, func() {}
	}
	t := &Trace{mu: &sync.Mutex{}, Operation: operation, PID: os.Getpid(), start: time.Now(), dir: dir}
	ctx = context.WithValue(ctx, key{}, t)
	Mark(ctx, "begin")
	return ctx, func() {
		Mark(ctx, "end")
		if record, ok := ctx.Value(recorderKey{}).(func(Trace)); ok {
			record(*t)
		}
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
	if Enabled(ctx) {
		MarkAt(ctx, name, time.Now())
	}
}

// MarkAt records a host-clock observation made by a transport goroutine.
// The owning startup goroutine appends it after receiving the response.
func MarkAt(ctx context.Context, name string, at time.Time) {
	if t, ok := ctx.Value(key{}).(*Trace); ok && !at.IsZero() {
		t.mu.Lock()
		defer t.mu.Unlock()
		t.Events = append(t.Events, Event{Name: name, Offset: at.Sub(t.start).Nanoseconds()})
	}
}

// Enabled lets the host request the matching guest's optional file diagnostics.
func Enabled(ctx context.Context) bool {
	_, ok := ctx.Value(key{}).(*Trace)
	return ok
}

// Runtime identifies the child for opt-in OS mapping/thread observations.
func Runtime(ctx context.Context, pid int) {
	if t, ok := ctx.Value(key{}).(*Trace); ok {
		t.RuntimePID = pid
	}
}

// ReadGuest copies an optional record after ready, without changing startup success.
// The benchmark validates its schema; old guests simply leave the scope absent.
func ReadGuest(ctx context.Context, transfer string) {
	if !Enabled(ctx) {
		return
	}
	data, err := os.ReadFile(filepath.Join(transfer, "startup-timing.json"))
	if err == nil {
		ReadGuestBytes(ctx, data)
	}
}

// ReadGuestBytes records linked guest diagnostics collected after worker join.
// The linked filesystem is private; diagnostics need not materialize on disk.
func ReadGuestBytes(ctx context.Context, data []byte) {
	if t, ok := ctx.Value(key{}).(*Trace); ok && len(data) <= 128*1024 && json.Valid(data) {
		t.Guest = append(json.RawMessage(nil), data...)
	}
}

// Work records logical bytes and file visits at an existing diagnostic boundary.
// Counters do not represent physical storage I/O or unique files.
func Work(ctx context.Context, name string, bytes, files int64) {
	if !Enabled(ctx) {
		return
	}
	t := ctx.Value(key{}).(*Trace)
	t.mu.Lock()
	defer t.mu.Unlock()
	t.Events = append(t.Events, Event{Name: name, Offset: time.Since(t.start).Nanoseconds(), BytesRead: bytes, FilesTouched: files})
}
