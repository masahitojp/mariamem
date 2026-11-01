package probe

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"net"
	"os"
	"path/filepath"
	"runtime/pprof"
	"sync"
	"sync/atomic"
	"time"
)

type WireSpan struct {
	WriteStartMS     float64 `json:"write_start_ms"`
	WriteEndMS       float64 `json:"write_end_ms"`
	FirstReadStartMS float64 `json:"first_read_start_ms"`
	FirstReadEndMS   float64 `json:"first_read_end_ms"`
	ReadBytes        int     `json:"read_bytes"`
	WriteBytes       int     `json:"write_bytes"`
	Reads            int     `json:"reads"`
	Writes           int     `json:"writes"`
}
type WireTracker struct {
	mu     sync.Mutex
	active bool
	start  time.Time
	span   WireSpan
}

func (w *WireTracker) startCount() {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.active = true
	w.start = time.Now()
	w.span = WireSpan{}
}
func (w *WireTracker) finish() WireSpan {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.active = false
	return w.span
}

type observedConn struct {
	net.Conn
	tracker *WireTracker
}

func ObserveConn(c net.Conn, w *WireTracker) net.Conn { return &observedConn{Conn: c, tracker: w} }
func (c *observedConn) Write(b []byte) (int, error) {
	at := time.Now()
	n, e := c.Conn.Write(b)
	end := time.Now()
	w := c.tracker
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.active {
		if w.span.Writes == 0 {
			w.span.WriteStartMS = ms(at.Sub(w.start))
			w.span.WriteEndMS = ms(end.Sub(w.start))
		}
		w.span.Writes++
		w.span.WriteBytes += n
	}
	return n, e
}
func (c *observedConn) Read(b []byte) (int, error) {
	at := time.Now()
	n, e := c.Conn.Read(b)
	end := time.Now()
	w := c.tracker
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.active {
		if w.span.Reads == 0 {
			w.span.FirstReadStartMS = ms(at.Sub(w.start))
			w.span.FirstReadEndMS = ms(end.Sub(w.start))
		}
		w.span.Reads++
		w.span.ReadBytes += n
	}
	return n, e
}

var stackDir string
var delayProbe bool
var captures atomic.Int32

type boundedText struct {
	b         []byte
	truncated bool
}

func (w *boundedText) Write(p []byte) (int, error) {
	n := len(p)
	left := (1 << 20) - len(w.b)
	if len(p) > left {
		p = p[:left]
		w.truncated = true
	}
	w.b = append(w.b, p...)
	return n, nil
}

func watchCount(index int) func() error {
	done := make(chan struct{})
	joined := make(chan error, 1)
	at := time.Now()
	go func() {
		timer := time.NewTimer(100 * time.Millisecond)
		defer timer.Stop()
		select {
		case <-done:
			joined <- nil
			return
		case <-timer.C:
		}
		if stackDir == "" || captures.Add(1) > 2 {
			joined <- nil
			return
		}
		start := time.Now()
		var buf boundedText
		err := pprof.Lookup("goroutine").WriteTo(&buf, 1)
		if err == nil {
			err = os.WriteFile(filepath.Join(stackDir, fmt.Sprintf("child-%03d.txt", index)), buf.b, 0600)
		}
		meta := map[string]any{"child": index, "trigger_ms": 100, "observed_after_ms": ms(start.Sub(at)), "capture_ms": ms(time.Since(start)), "bytes": len(buf.b), "truncated": buf.truncated, "delayed_pilot": delayProbe}
		data, j := json.MarshalIndent(meta, "", "  ")
		err = errors.Join(err, j)
		if err == nil {
			err = os.WriteFile(filepath.Join(stackDir, fmt.Sprintf("child-%03d.json", index)), append(data, '\n'), 0600)
		}
		joined <- err
	}()
	return func() error { close(done); return <-joined }
}

func countObserved(ctx context.Context, c *sql.Conn, w *WireTracker, index int, s *Sample) (err error) {
	defer base.DiagBegin(nil, "client_count", int64(index), 0, 0)()
	stop := watchCount(index)
	defer func() { err = errors.Join(err, stop()) }()
	w.startCount()
	defer func() { s.WireResult = w.finish() }()
	pprof.Do(ctx, pprof.Labels("operation", "count_sum"), func(ctx context.Context) {
		at := time.Now()
		if delayProbe {
			time.Sleep(150 * time.Millisecond)
		}
		rows, e := c.QueryContext(ctx, "SELECT COUNT(*),SUM(v) FROM fork_probe")
		s.QueryMS = ms(time.Since(at))
		if e != nil {
			err = e
			return
		}
		defer func() { err = errors.Join(err, rows.Close()) }()
		at = time.Now()
		var n, total int
		if !rows.Next() {
			err = errors.Join(fmt.Errorf("missing aggregate row"), rows.Err())
			return
		}
		if e = rows.Scan(&n, &total); e != nil {
			err = e
			return
		}
		s.FirstRowMS = ms(time.Since(at))
		at = time.Now()
		if rows.Next() {
			err = fmt.Errorf("unexpected aggregate row")
			return
		}
		if e = rows.Err(); e != nil {
			err = e
			return
		}
		if e = rows.Close(); e != nil {
			err = e
			return
		}
		s.DrainMS = ms(time.Since(at))
		if n != 1000 || total != 500500 {
			err = fmt.Errorf("pristine oracle: count=%d sum=%d", n, total)
		}
	})
	return err
}
