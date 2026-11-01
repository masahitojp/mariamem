// Package probe observes public lifecycle resource costs. Darwin-only campaign.
package probe

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"runtime"
	"runtime/debug"
	"strings"
	"syscall"
	"time"
)

type Database struct {
	Open     func(string) (*sql.DB, error)
	Snapshot func(context.Context, int) (*Snapshot, error)
	Wait     func(context.Context) error
	Close    func() error
}
type Snapshot struct {
	Fork  func(context.Context) (*Database, error)
	Close func() error
}
type Counters struct {
	CPUms        float64 `json:"cpu_ms"`
	UserMS       float64 `json:"user_ms"`
	SystemMS     float64 `json:"system_ms"`
	MaxRSS       int64   `json:"max_rss_bytes"`
	TotalAlloc   uint64  `json:"total_alloc_bytes"`
	HeapAlloc    uint64  `json:"heap_alloc_bytes"`
	HeapInuse    uint64  `json:"heap_inuse_bytes"`
	HeapSys      uint64  `json:"heap_sys_bytes"`
	HeapReleased uint64  `json:"heap_released_bytes"`
	Sys          uint64  `json:"go_sys_bytes"`
	Mallocs      uint64  `json:"mallocs"`
	NumGC        uint32  `json:"num_gc"`
	Goroutines   int     `json:"goroutines"`
}

func counters() Counters {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	var r syscall.Rusage
	if e := syscall.Getrusage(syscall.RUSAGE_SELF, &r); e != nil {
		panic(e)
	}
	u := float64(r.Utime.Sec)*1000 + float64(r.Utime.Usec)/1000
	s := float64(r.Stime.Sec)*1000 + float64(r.Stime.Usec)/1000
	return Counters{u + s, u, s, r.Maxrss, m.TotalAlloc, m.HeapAlloc, m.HeapInuse, m.HeapSys, m.HeapReleased, m.Sys, m.Mallocs, m.NumGC, runtime.NumGoroutine()}
}

type Phase struct {
	Name       string   `json:"name"`
	Child      int      `json:"child"`
	WallMS     float64  `json:"wall_ms"`
	CPUms      float64  `json:"cpu_ms"`
	AllocBytes uint64   `json:"alloc_bytes"`
	Mallocs    uint64   `json:"mallocs"`
	GC         uint32   `json:"gc_count"`
	Before     Counters `json:"before"`
	After      Counters `json:"after"`
}
type Event struct {
	Stage    string   `json:"stage"`
	Children int      `json:"children"`
	Metrics  Counters `json:"metrics"`
	Phases   []Phase  `json:"phases"`
}
type Result struct {
	Backend    string  `json:"backend"`
	PID        int     `json:"pid"`
	Version    string  `json:"server_version"`
	Go         string  `json:"go"`
	GOMAXPROCS int     `json:"gomaxprocs"`
	Success    bool    `json:"success"`
	Cleanup    bool    `json:"cleanup_complete"`
	Corrupt    bool    `json:"corrupt_seed"`
	Error      string  `json:"error,omitempty"`
	Events     []Event `json:"events"`
}

var phases []Phase

func measure(name string, child int, f func() error) error {
	before := counters()
	at := time.Now()
	e := f()
	wall := float64(time.Since(at)) / 1e6
	after := counters()
	phases = append(phases, Phase{name, child, wall, after.CPUms - before.CPUms, after.TotalAlloc - before.TotalAlloc, after.Mallocs - before.Mallocs, after.NumGC - before.NumGC, before, after})
	return e
}

var input = bufio.NewScanner(os.Stdin)

func checkpoint(r *Result, stage string, n int) error {
	e := Event{stage, n, counters(), phases}
	phases = nil
	r.Events = append(r.Events, e)
	if err := json.NewEncoder(os.Stdout).Encode(e); err != nil {
		return err
	}
	if !input.Scan() || input.Text() != "continue" {
		return errors.New("controller acknowledgement missing")
	}
	return nil
}
func retire(d *Database, p *sql.DB) error {
	var e error
	if p != nil {
		e = errors.Join(e, p.Close())
	}
	if d != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		defer cancel()
		if d.Wait != nil {
			e = errors.Join(e, d.Wait(ctx))
		}
		e = errors.Join(e, d.Close())
	}
	return e
}
func check(ctx context.Context, p *sql.DB) error {
	var n, sum int
	if e := p.QueryRowContext(ctx, "SELECT COUNT(*),SUM(v) FROM fork_probe").Scan(&n, &sum); e != nil {
		return e
	}
	if n != 1000 || sum != 500500 {
		return fmt.Errorf("pristine oracle: count=%d sum=%d", n, sum)
	}
	return nil
}
func connect(ctx context.Context, d *Database) (*sql.DB, error) {
	p, e := d.Open("tcp")
	if e != nil {
		return nil, e
	}
	p.SetMaxOpenConns(1)
	p.SetMaxIdleConns(1)
	var one int
	e = p.QueryRowContext(ctx, "SELECT 1").Scan(&one)
	if e == nil && one != 1 {
		e = fmt.Errorf("SELECT1=%d", one)
	}
	if e != nil {
		return nil, errors.Join(e, p.Close())
	}
	return p, nil
}
func run(r *Result, start func(context.Context) (*Database, error)) (err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	var root *Database
	var pool *sql.DB
	var sn *Snapshot
	children := make([]*Database, 0, 4)
	defer func() {
		e := retire(root, pool)
		for _, d := range children {
			e = errors.Join(e, retire(d, nil))
		}
		if sn != nil {
			e = errors.Join(e, sn.Close())
		}
		r.Cleanup = e == nil
		err = errors.Join(err, e)
	}()
	if e := checkpoint(r, "process", 0); e != nil {
		return e
	}
	if e := measure("noop", 0, func() error { return nil }); e != nil {
		return e
	}
	if e := measure("root_start", 0, func() error { var e error; root, e = start(ctx); return e }); e != nil {
		return e
	}
	var e error
	pool, e = connect(ctx, root)
	if e != nil {
		return e
	}
	if e = pool.QueryRowContext(ctx, "SELECT VERSION()").Scan(&r.Version); e != nil {
		return e
	}
	if _, e = pool.ExecContext(ctx, "CREATE TABLE fork_probe (id INTEGER PRIMARY KEY,v INTEGER NOT NULL)"); e != nil {
		return e
	}
	values := make([]string, 1000)
	for i := range values {
		values[i] = fmt.Sprintf("(%d,%d)", i+1, i+1)
	}
	if _, e = pool.ExecContext(ctx, "INSERT INTO fork_probe VALUES "+strings.Join(values, ",")); e != nil {
		return e
	}
	if e = check(ctx, pool); e != nil {
		return e
	}
	if r.Corrupt {
		if _, e = pool.ExecContext(ctx, "UPDATE fork_probe SET v=-1 WHERE id=1"); e != nil {
			return e
		}
	}
	if e = pool.Close(); e != nil {
		return e
	}
	pool = nil
	if root.Wait != nil {
		if e = root.Wait(ctx); e != nil {
			return e
		}
	}
	if e = checkpoint(r, "root_seeded", 0); e != nil {
		return e
	}
	if e = measure("snapshot_and_source_close", 0, func() error {
		var e error
		sn, e = root.Snapshot(ctx, 4)
		if e != nil {
			return e
		}
		e = root.Close()
		if e == nil {
			root = nil
		}
		return e
	}); e != nil {
		return e
	}
	if e = checkpoint(r, "baseline_natural", 0); e != nil {
		return e
	}
	if e = measure("baseline_gc", 0, func() error { runtime.GC(); return nil }); e != nil {
		return e
	}
	if e = checkpoint(r, "baseline_gc", 0); e != nil {
		return e
	}
	for i := 1; i <= 4; i++ {
		var d *Database
		if e = measure("fork", i, func() error { var e error; d, e = sn.Fork(ctx); return e }); e != nil {
			return e
		}
		children = append(children, d)
		if e = measure("connect_select_oracle_retire_connection", i, func() error {
			p, e := connect(ctx, d)
			if e != nil {
				return e
			}
			e = check(ctx, p)
			e = errors.Join(e, p.Close())
			if d.Wait != nil {
				e = errors.Join(e, d.Wait(ctx))
			}
			return e
		}); e != nil {
			return e
		}
		if i == 1 || i == 2 || i == 4 {
			if e = checkpoint(r, fmt.Sprintf("held_%d", i), i); e != nil {
				return e
			}
			if e = measure("idle_500ms", i, func() error { time.Sleep(500 * time.Millisecond); return nil }); e != nil {
				return e
			}
			if e = checkpoint(r, fmt.Sprintf("held_%d_idle", i), i); e != nil {
				return e
			}
		}
	}
	// Separate live retained memory from garbage; do not include this GC in Fork timing.
	if e = measure("held_4_gc", 4, func() error { runtime.GC(); return nil }); e != nil {
		return e
	}
	if e = checkpoint(r, "held_4_gc", 4); e != nil {
		return e
	}
	// All children remain independent while retained; query connections are temporary.
	for i, d := range children {
		p, e := connect(ctx, d)
		if e != nil {
			return e
		}
		if e = check(ctx, p); e != nil {
			return errors.Join(e, p.Close())
		}
		_, e = p.ExecContext(ctx, fmt.Sprintf("UPDATE fork_probe SET v=%d WHERE id=1", -i-1))
		e = errors.Join(e, p.Close())
		if e != nil {
			return e
		}
		if d.Wait != nil {
			if e = d.Wait(ctx); e != nil {
				return e
			}
		}
	}
	for i, d := range children {
		p, e := connect(ctx, d)
		if e != nil {
			return e
		}
		var v int
		e = p.QueryRowContext(ctx, "SELECT v FROM fork_probe WHERE id=1").Scan(&v)
		e = errors.Join(e, p.Close())
		if e != nil {
			return e
		}
		if v != -i-1 {
			return fmt.Errorf("isolation oracle child=%d value=%d", i+1, v)
		}
		if d.Wait != nil {
			if e = d.Wait(ctx); e != nil {
				return e
			}
		}
	}
	if e = checkpoint(r, "held_4_mutated", 4); e != nil {
		return e
	}
	if e = measure("close_children", 0, func() error {
		for i, d := range children {
			if e := d.Close(); e != nil {
				return e
			}
			children[i] = nil
		}
		children = nil
		return nil
	}); e != nil {
		return e
	}
	if e = checkpoint(r, "closed_children_natural", 0); e != nil {
		return e
	}
	if e = measure("post_close_gc", 0, func() error { runtime.GC(); return nil }); e != nil {
		return e
	}
	if e = checkpoint(r, "closed_children_gc", 0); e != nil {
		return e
	}
	if e = measure("post_close_scavenge", 0, func() error { debug.FreeOSMemory(); return nil }); e != nil {
		return e
	}
	if e = checkpoint(r, "closed_children_scavenge", 0); e != nil {
		return e
	}
	// Check the baseline survived all four independent mutations (excluded from fork summary).
	d, e := sn.Fork(ctx)
	if e != nil {
		return e
	}
	p, e := connect(ctx, d)
	if e != nil {
		return errors.Join(e, retire(d, nil))
	}
	e = check(ctx, p)
	e = errors.Join(e, retire(d, p))
	if e != nil {
		return e
	}
	if e = sn.Close(); e != nil {
		return e
	}
	sn = nil
	if e = checkpoint(r, "closed_all_natural", 0); e != nil {
		return e
	}
	debug.FreeOSMemory()
	return checkpoint(r, "closed_all_scavenge", 0)
}
func Main(backend string, start func(context.Context) (*Database, error)) {
	r := Result{Backend: backend, PID: os.Getpid(), Go: runtime.Version(), GOMAXPROCS: runtime.GOMAXPROCS(0)}
	flag.BoolVar(&r.Corrupt, "corrupt-seed", false, "negative fixture oracle")
	out := flag.String("out", "", "report path")
	flag.Parse()
	if runtime.GOOS != "darwin" || *out == "" {
		panic("Darwin resource campaign requires -out")
	}
	e := run(&r, start)
	r.Success = e == nil
	if e != nil {
		r.Error = e.Error()
	}
	data, j := json.MarshalIndent(r, "", "  ")
	if j == nil {
		j = os.WriteFile(*out, append(data, '\n'), 0600)
	}
	if e != nil || j != nil {
		fmt.Fprintln(os.Stderr, errors.Join(e, j))
		os.Exit(1)
	}
}
