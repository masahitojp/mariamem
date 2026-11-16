// Package trace records what the model-case suite does and when, so the
// benchmark can show every node of the two execution models on one time
// axis. A span is one node: booting the server, importing the schema,
// taking the snapshot, forking, loading sample data, resetting, or one
// test's body. Lanes group spans that belong together (one test, the
// shared copy, the setup in TestMain).
package trace

import (
	"encoding/json"
	"os"
	"sync"
	"time"
)

type Span struct {
	Name    string  `json:"name"`
	Kind    string  `json:"kind"`
	Lane    string  `json:"lane"`
	StartMS float64 `json:"start_ms"`
	EndMS   float64 `json:"end_ms"`
}

type Trace struct {
	Meta      map[string]string `json:"meta"`
	ElapsedMS float64           `json:"elapsed_ms"`
	Spans     []Span            `json:"spans"`
}

type Recorder struct {
	mu    sync.Mutex
	t0    time.Time
	meta  map[string]string
	spans []Span
}

func New() *Recorder { return &Recorder{t0: time.Now(), meta: map[string]string{}} }

// Start opens a span; the returned func closes it.
func (r *Recorder) Start(name, kind, lane string) func() {
	start := time.Since(r.t0)
	return func() {
		end := time.Since(r.t0)
		r.mu.Lock()
		r.spans = append(r.spans, Span{Name: name, Kind: kind, Lane: lane, StartMS: ms(start), EndMS: ms(end)})
		r.mu.Unlock()
	}
}

func (r *Recorder) Set(key, value string) {
	r.mu.Lock()
	r.meta[key] = value
	r.mu.Unlock()
}

// Write stores the trace as JSON. An empty path writes nothing.
func (r *Recorder) Write(path string) error {
	if path == "" {
		return nil
	}
	r.mu.Lock()
	t := Trace{Meta: r.meta, ElapsedMS: ms(time.Since(r.t0)), Spans: append([]Span(nil), r.spans...)}
	r.mu.Unlock()
	b, err := json.MarshalIndent(t, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o644)
}

func ms(d time.Duration) float64 { return float64(d.Microseconds()) / 1000 }
