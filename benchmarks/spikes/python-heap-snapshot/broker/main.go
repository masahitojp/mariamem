// Isolated experiment controller. One root lineage per process, separate Go DB
// instances and endpoints. Lifecycle requests are serialized; SQL stays direct.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	mm "github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/spikes/python-heap-snapshot/metrics"
	"github.com/masahitojp/mariamem/internal/generatedgo"
	"github.com/masahitojp/mariamem/internal/prepared"
	"os"
	"os/signal"
	"syscall"
	"time"
)

type request struct {
	ID              int     `json:"id"`
	Op              string  `json:"op"`
	Handle          int     `json:"handle"`
	Rollback        bool    `json:"rollback"`
	Timeout         float64 `json:"timeout"`
	QueryTimeout    float64 `json:"query_timeout"`
	StartupTimeout  float64 `json:"startup_timeout"`
	ShutdownTimeout float64 `json:"shutdown_timeout"`
	Fault           string  `json:"fault"`
}
type manager struct {
	seq   int
	dbs   map[int]*mm.Database
	snaps map[int]*mm.Snapshot
}

func (m *manager) next() int { m.seq++; return m.seq }
func endpoint(id int, d *mm.Database) map[string]any {
	c := d.ConnectionInfo()
	return map[string]any{"handle": id, "host": c.Host, "port": c.Port, "user": c.User, "password": c.Password, "database": c.Database, "pid": os.Getpid()}
}
func (m *manager) call(r request) (map[string]any, error) {
	result := map[string]any{}
	timeout := r.Timeout
	if timeout <= 0 {
		timeout = 120
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout*float64(time.Second)))
	defer cancel()
	switch r.Op {
	case "start":
		if m.seq != 0 {
			return result, errors.New("one root lineage per broker")
		}
		d, e := mm.Start(ctx, mm.Options{QueryTimeout: time.Duration(r.QueryTimeout * float64(time.Second)), StartupTimeout: time.Duration(r.StartupTimeout * float64(time.Second)), ShutdownTimeout: time.Duration(r.ShutdownTimeout * float64(time.Second))})
		if e != nil {
			return result, e
		}
		id := m.next()
		m.dbs[id] = d
		result["database"] = endpoint(id, d)
	case "snapshot":
		d := m.dbs[r.Handle]
		if d == nil {
			return result, mm.ErrClosed
		}
		if r.Fault != "" {
			os.Setenv("MARIAMEM_HEAP_FAULT", r.Fault)
			defer os.Unsetenv("MARIAMEM_HEAP_FAULT")
		}
		s, e := d.Snapshot(ctx, mm.SnapshotOptions{Rollback: r.Rollback})
		result["closed"] = d.Closed()
		if d.Closed() {
			delete(m.dbs, r.Handle)
		}
		if e != nil {
			return result, e
		}
		id := m.next()
		m.snaps[id] = s
		result["snapshot"] = id
		if os.Getenv("MARIAMEM_HEAP") == "1" {
			result["heap_stats"] = s.ExperimentHeapStats()
		}
	case "fork":
		s := m.snaps[r.Handle]
		if s == nil {
			return result, mm.ErrClosed
		}
		d, e := s.Fork(ctx)
		if e != nil {
			return result, e
		}
		id := m.next()
		m.dbs[id] = d
		result["database"] = endpoint(id, d)
	case "db_close":
		d := m.dbs[r.Handle]
		if d == nil {
			return result, nil
		}
		e := d.Close()
		delete(m.dbs, r.Handle)
		result["closed"] = true
		return result, e
	case "snapshot_close":
		s := m.snaps[r.Handle]
		if s == nil {
			return result, nil
		}
		e := s.Close()
		delete(m.snaps, r.Handle)
		return result, e
	case "wait_disconnected":
		d := m.dbs[r.Handle]
		if d == nil {
			return result, mm.ErrClosed
		}
		return result, d.WaitDisconnected(ctx)
	case "verify":
		s := m.snaps[r.Handle]
		if s == nil {
			return result, mm.ErrClosed
		}
		return result, s.ExperimentHeapVerify()
	case "stats":
		result["resources"] = metrics.Read()
		result["dbs"] = len(m.dbs)
		result["snapshots"] = len(m.snaps)
		result["capture_requests"] = prepared.HeapRequests()
	default:
		return result, fmt.Errorf("unsupported experiment operation %q", r.Op)
	}
	return result, nil
}
func (m *manager) close() {
	for id, d := range m.dbs {
		if e := d.Close(); e != nil {
			fmt.Fprintln(os.Stderr, e)
		}
		delete(m.dbs, id)
	}
	for id, s := range m.snaps {
		if e := s.Close(); e != nil {
			fmt.Fprintln(os.Stderr, e)
		}
		delete(m.snaps, id)
	}
}
func run() error {
	defer metrics.Save()
	m := &manager{dbs: map[int]*mm.Database{}, snaps: map[int]*mm.Snapshot{}}
	defer m.close()
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	enc := json.NewEncoder(os.Stdout)
	if e := enc.Encode(map[string]any{"event": "ready", "protocol": 1, "pid": os.Getpid(), "guest_sha256": generatedgo.GuestSHA256}); e != nil {
		return e
	}
	lines := make(chan []byte)
	go func() {
		defer close(lines)
		s := bufio.NewScanner(os.Stdin)
		s.Buffer(make([]byte, 4096), 65536)
		for s.Scan() {
			b := append([]byte{}, s.Bytes()...)
			select {
			case lines <- b:
			case <-ctx.Done():
				return
			}
		}
	}()
	for {
		select {
		case <-ctx.Done():
			return nil
		case b, ok := <-lines:
			if !ok {
				return nil
			}
			var r request
			if e := json.Unmarshal(b, &r); e != nil {
				return e
			}
			out, e := m.call(r)
			out["id"] = r.ID
			out["ok"] = e == nil
			if e != nil {
				code := "experiment_error"
				var he *mm.HostError
				if errors.As(e, &he) {
					code = he.Code
					out["closed"] = he.Closed
				} else if errors.Is(e, mm.ErrClosed) {
					code = "closed"
				}
				out["error"] = map[string]any{"code": code, "message": e.Error()}
			}
			idle := len(m.dbs) == 0 && len(m.snaps) == 0
			out["idle"] = idle
			out["capture_requests"] = prepared.HeapRequests()
			if e := enc.Encode(out); e != nil {
				return e
			}
			if idle {
				return nil
			}
		}
	}
}
func main() {
	if e := run(); e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
