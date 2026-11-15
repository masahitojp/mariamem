//go:build closeeval

package mariamem

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"testing"
	"time"

	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

// Diagnostic overlays change only this constant; the plain binary has no
// per-stage clocks, observers or mapping samples in its child loop.
const evalDiagnostic = false

type evalEvent struct {
	NS      int64  `json:"ns"`
	Kind    string `json:"kind"`
	ID      int    `json:"id"`
	Worker  int    `json:"worker"`
	Active  uint64 `json:"active_mappings"`
	Pending int    `json:"pending_cleanup"`
}
type evalTrace struct {
	mu                  sync.Mutex
	begin               time.Time
	events              []evalEvent
	pending, maxPending int
	maxMappings         uint64
}

func (d *evalTrace) mark(kind string, id, worker, delta int) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.pending += delta
	if d.pending > d.maxPending {
		d.maxPending = d.pending
	}
	active := base.MemoryMappingStats()["active_mappings"]
	if active > d.maxMappings {
		d.maxMappings = active
	}
	d.events = append(d.events, evalEvent{time.Since(d.begin).Nanoseconds(), kind, id, worker, active, d.pending})
}

type evalBackend struct {
	backend
	trace      *evalTrace
	id, worker int
}

func (b evalBackend) CloseWithStopped(ctx context.Context, notify func(error)) error {
	pending := false
	defer func() {
		delta := 0
		if pending {
			delta = -1
		}
		b.trace.mark("backend_cleanup_end", b.id, b.worker, delta)
	}()
	return b.backend.(interface {
		CloseWithStopped(context.Context, func(error)) error
	}).CloseWithStopped(ctx, func(err error) {
		if err == nil {
			pending = true
			b.trace.mark("stopped", b.id, b.worker, 1)
		}
		notify(err)
	})
}

// Embedding backend otherwise hides the concrete server's disposal oracle.
func (b evalBackend) DisposalComplete() bool {
	return b.backend.(interface{ DisposalComplete() bool }).DisposalComplete()
}

func evalSQL(db *Database) (*sql.DB, error) {
	cfg := mysql.NewConfig()
	info := db.ConnectionInfo()
	cfg.User = info.User
	cfg.Passwd = info.Password
	cfg.DBName = info.Database
	cfg.Net = "tcp"
	cfg.Addr = net.JoinHostPort(info.Host, strconv.Itoa(info.Port))
	cfg.InterpolateParams = true
	cfg.DialFunc = db.DialContext
	c, err := mysql.NewConnector(cfg)
	if err != nil {
		return nil, err
	}
	pool := sql.OpenDB(c)
	pool.SetMaxOpenConns(1)
	return pool, nil
}
func evalCPU() float64 {
	var r syscall.Rusage
	if err := syscall.Getrusage(syscall.RUSAGE_SELF, &r); err != nil {
		panic(err)
	}
	return float64(r.Utime.Sec+r.Stime.Sec)*1000 + float64(r.Utime.Usec+r.Stime.Usec)/1000
}

func TestCloseEvaluation(t *testing.T) {
	if os.Getenv("CLOSE_EVAL") != "1" {
		t.Skip("explicit finite campaign only")
	}
	p, err := strconv.Atoi(os.Getenv("CLOSE_P"))
	if err != nil {
		t.Fatal(err)
	}
	cap, err := strconv.Atoi(os.Getenv("CLOSE_CAP"))
	if err != nil {
		t.Fatal(err)
	}
	mode := os.Getenv("CLOSE_MODE")
	if (p != 1 && p != 2) || (cap != p && cap != 2*p) || (mode != "sync" && mode != "stop") {
		t.Fatal("invalid fixed campaign cell")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	prep := time.Now()
	root, err := Start(ctx, Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer root.Close()
	pool, err := evalSQL(root)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = pool.ExecContext(ctx, "CREATE TABLE close_rows(id INT PRIMARY KEY,v INT NOT NULL)"); err != nil {
		t.Fatal(err)
	}
	var values []string
	for i := 0; i < 1000; i++ {
		values = append(values, fmt.Sprintf("(%d,%d)", i, i))
	}
	if _, err = pool.ExecContext(ctx, "INSERT INTO close_rows VALUES "+strings.Join(values, ",")); err != nil {
		t.Fatal(err)
	}
	if err = pool.Close(); err != nil {
		t.Fatal(err)
	}
	if err = root.WaitDisconnected(ctx); err != nil {
		t.Fatal(err)
	}
	snap, err := root.Snapshot(ctx, SnapshotOptions{MaxForks: cap})
	if err != nil {
		t.Fatal(err)
	}
	defer snap.Close()
	if err = root.Close(); err != nil {
		t.Fatal(err)
	}
	preparationMS := float64(time.Since(prep)) / 1e6
	before := base.MemoryMappingStats()
	handles := make([]*closeOperation, 48)
	var next atomic.Int32
	var wg sync.WaitGroup
	errs := make(chan error, p)
	start := time.Now()
	cpuStart := evalCPU()
 var runtimeDirs atomic.Int32
	trace := &evalTrace{begin: start}
	worker := func(w int) error {
		for {
			id := int(next.Add(1)) - 1
			if id >= 48 {
				return nil
			}
			var db *Database
			var err error
			if evalDiagnostic {
				trace.mark("fork_request", id, w, 0)
				lease, e := snap.forkLimit().Acquire(ctx)
				if e != nil {
					return e
				}
				trace.mark("fork_admitted", id, w, 0)
				db, err = snap.forkReserved(ctx, lease)
			} else {
				db, err = snap.Fork(ctx)
			}
			if err != nil {
				return err
			}
			if db.temporary != "" { runtimeDirs.Add(1) }
			if evalDiagnostic {
				trace.mark("fork_ready", id, w, 0)
				db.mu.Lock()
				db.server = evalBackend{db.server, trace, id, w}
				db.mu.Unlock()
			}
			if err := func() error {
				pool, e := evalSQL(db)
				if e != nil {
					return e
				}
				defer pool.Close()
				var count, total int
				if e = pool.QueryRowContext(ctx, "SELECT COUNT(*),SUM(v) FROM close_rows").Scan(&count, &total); e != nil {
					return e
				}
				if count != 1000 || total != 499500 {
					return fmt.Errorf("child %d snapshot isolation: %d/%d", id, count, total)
				}
				if _, e = pool.ExecContext(ctx, "UPDATE close_rows SET v=v+1 WHERE id=0"); e != nil {
					return e
				}
				var value int
				if e = pool.QueryRowContext(ctx, "SELECT v FROM close_rows WHERE id=0").Scan(&value); e != nil {
					return e
				}
				if value != 1 {
					return fmt.Errorf("child mutation: %d", value)
				}
				if e = pool.Close(); e != nil {
					return e
				}
				return db.WaitDisconnected(ctx)
			}(); err != nil {
				db.Close()
				return err
			}
			if evalDiagnostic {
				trace.mark("close_begin", id, w, 0)
			}
			if mode == "sync" {
				err = db.Close()
				db.mu.Lock()
				handles[id] = db.closing
				db.mu.Unlock()
			} else {
				handles[id], err = db.stopForCleanup(ctx)
			}
			if evalDiagnostic {
				trace.mark("close_return", id, w, 0)
			}
			if err != nil {
				db.Close()
				return err
			}
		}
	}
	for w := 0; w < p; w++ {
		wg.Add(1)
		go func(w int) { defer wg.Done(); errs <- worker(w) }(w)
	}
	wg.Wait()
	workDone := time.Now()
	close(errs)
	var failures []string
	for err := range errs {
		if err != nil {
			failures = append(failures, err.Error())
		}
	}
	// The final drain is part of the primary timer and independent of worker waits.
	for id, op := range handles {
		if op == nil {
			failures = append(failures, fmt.Sprintf("missing cleanup handle %d", id))
			continue
		}
		if err := op.Wait(ctx); err != nil {
			failures = append(failures, err.Error())
		}
		if !op.Disposed() {
			failures = append(failures, fmt.Sprintf("undisposed child %d", id))
		}
	}
	_, occupied := snap.forkLimit().Usage()
	if occupied != 0 {
		failures = append(failures, fmt.Sprintf("retained leases %d", occupied))
	}
	if err := snap.Close(); err != nil {
		failures = append(failures, err.Error())
	}
	end := time.Now()
	cpuEnd := evalCPU()
	after := base.MemoryMappingStats()
	if after["active_mappings"] != before["active_mappings"] {
		failures = append(failures, "linear mapping count did not return to baseline")
	}
	record := map[string]any{"runtime_directory_count": runtimeDirs.Load(), "mode": mode, "p": p, "cap": cap, "children": 48, "rows": 1000, "diagnostic": evalDiagnostic, "preparation_ms": preparationMS, "batch_drain_ms": float64(end.Sub(start)) / 1e6, "workers_ms": float64(workDone.Sub(start)) / 1e6, "drain_ms": float64(end.Sub(workDone)) / 1e6, "batch_cpu_ms": cpuEnd - cpuStart, "mappings_before": before, "mappings_after": after, "failures": failures}
	if evalDiagnostic {
		record["events"] = trace.events
		record["max_pending_backend_cleanup"] = trace.maxPending
		record["max_sampled_active_mappings"] = trace.maxMappings
	}
	raw, err := json.Marshal(record)
	if err != nil {
		t.Fatal(err)
	}
	fmt.Println("CLOSE_RESULT " + string(raw))
	if len(failures) > 0 {
		t.Fatal(failures)
	}
}
