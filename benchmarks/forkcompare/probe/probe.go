// Package probe measures public readiness boundaries without changing either engine.
package probe

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"runtime/pprof"
	"strings"
	"sync"
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
type Sample struct {
	RetireMS  float64        `json:"retire_ms"`
	WaitMS    float64        `json:"wait_ms"`
	CloseMS   float64        `json:"close_ms"`
	WaitTrace map[string]any `json:"wait_trace,omitempty"`

	OffsetMS  float64 `json:"offset_ms"`
	TotalMS   float64 `json:"total_ms"`
	SQLMS     float64 `json:"sql_ms"`
	Cleanup   bool    `json:"cleanup_complete"`
	Index     int     `json:"index"`
	ForkMS    float64 `json:"fork_ms"`
	ConnectMS float64 `json:"connect_ms"`
	SelectMS  float64 `json:"select_ms"`
	ReadyMS   float64 `json:"ready_ms"`
	CleanupMS float64 `json:"cleanup_ms"`
	Oracle    bool    `json:"oracle"`
	Error     string  `json:"error,omitempty"`
}
type Report struct {
	CPUUserMS           float64  `json:"cpu_user_ms"`
	CPUSystemMS         float64  `json:"cpu_system_ms"`
	MinorFaults         int64    `json:"minor_faults"`
	MajorFaults         int64    `json:"major_faults"`
	VoluntarySwitches   int64    `json:"voluntary_switches"`
	InvoluntarySwitches int64    `json:"involuntary_switches"`
	LifetimeMaxRSSBytes int64    `json:"lifetime_max_rss_bytes"`
	SyncDir             string   `json:"-"`
	Backend             string   `json:"backend"`
	Route               string   `json:"route"`
	Parallel            int      `json:"parallel"`
	Count               int      `json:"count"`
	Go                  string   `json:"go"`
	GOMAXPROCS          int      `json:"gomaxprocs"`
	Version             string   `json:"server_version"`
	StartMS             float64  `json:"root_start_ms"`
	SnapshotMS          float64  `json:"snapshot_ms"`
	BatchMS             float64  `json:"batch_ms"`
	Samples             []Sample `json:"samples"`
	RootClosed          bool     `json:"root_closed_before_forks"`
	Cleanup             bool     `json:"cleanup_complete"`
	Corrupt             bool     `json:"corrupt_seed"`
	Success             bool     `json:"success"`
	Error               string   `json:"error,omitempty"`
}

func ms(t time.Duration) float64                       { return float64(t) / 1e6 }
func retire(d *Database, p *sql.DB, c *sql.Conn) error { return retireMeasured(d, p, c, nil) }
func retireMeasured(d *Database, p *sql.DB, c *sql.Conn, sample *Sample) error {
	at := time.Now()
	var e error
	if c != nil {
		e = errors.Join(e, c.Close())
	}
	if p != nil {
		e = errors.Join(e, p.Close())
	}
	if sample != nil {
		sample.RetireMS = ms(time.Since(at))
	}
	if d != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		if sample != nil && os.Getenv("ISSUE117_TRACE") == "1" {
			ctx = context.WithValue(ctx, "issue117_wait_record", func(trace map[string]any) { sample.WaitTrace = trace })
		}
		at = time.Now()
		if d.Wait != nil {
			e = errors.Join(e, d.Wait(ctx))
		}
		if sample != nil {
			sample.WaitMS = ms(time.Since(at))
		}
		at = time.Now()
		e = errors.Join(e, d.Close())
		if sample != nil {
			sample.CloseMS = ms(time.Since(at))
		}
	}
	return e
}
func oracle(ctx context.Context, q interface {
	QueryRowContext(context.Context, string, ...any) *sql.Row
}) error {
	var n, total int
	if e := q.QueryRowContext(ctx, "SELECT COUNT(*),SUM(v) FROM fork_probe").Scan(&n, &total); e != nil {
		return e
	}
	if n != 1000 || total != 500500 {
		return fmt.Errorf("pristine oracle: count=%d sum=%d", n, total)
	}
	return nil
}
func one(ctx context.Context, sn *Snapshot, route string, index int, batchStart time.Time) (s Sample, err error) {
	ctx = context.WithValue(ctx, "forkstages_child", index)
	s.Index = index
	s.Cleanup = true
	begin := time.Now()
	s.OffsetMS = ms(begin.Sub(batchStart))
	defer func() { s.TotalMS = ms(time.Since(begin)) }()
	d, e := sn.Fork(ctx)
	s.ForkMS = ms(time.Since(begin))
	if e != nil {
		return s, e
	}
	var p *sql.DB
	var c *sql.Conn
	defer func() {
		at := time.Now()
		cleanupErr := retireMeasured(d, p, c, &s)
		s.Cleanup = cleanupErr == nil
		err = errors.Join(err, cleanupErr)
		s.CleanupMS = ms(time.Since(at))
	}()
	at := time.Now()
	p, e = d.Open(route)
	if e != nil {
		return s, e
	}
	p.SetMaxOpenConns(1)
	p.SetMaxIdleConns(1)
	c, e = p.Conn(ctx)
	s.ConnectMS = ms(time.Since(at))
	if e != nil {
		return s, e
	}
	at = time.Now()
	var value int
	e = c.QueryRowContext(ctx, "SELECT 1").Scan(&value)
	s.SelectMS = ms(time.Since(at))
	s.ReadyMS = ms(time.Since(begin))
	if e != nil {
		return s, e
	}
	if value != 1 {
		return s, fmt.Errorf("SELECT1=%d", value)
	}
	sqlAt := time.Now()
	defer func() { s.SQLMS = ms(time.Since(sqlAt)) }()
	if e = oracle(ctx, c); e != nil {
		return s, e
	}
	result, e := c.ExecContext(ctx, "UPDATE fork_probe SET v=-1 WHERE id=1")
	if e != nil {
		return s, e
	}
	n, e := result.RowsAffected()
	if e != nil || n != 1 {
		return s, fmt.Errorf("mutation affected=%d: %v", n, e)
	}
	if e = c.QueryRowContext(ctx, "SELECT v FROM fork_probe WHERE id=1").Scan(&value); e != nil {
		return s, e
	}
	if value != -1 {
		return s, fmt.Errorf("mutation value=%d", value)
	}
	s.Oracle = true
	return s, nil
}
func run(r *Report, start func(context.Context) (*Database, error)) (err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	at := time.Now()
	root, e := start(ctx)
	r.StartMS = ms(time.Since(at))
	if e != nil {
		return e
	}
	var pool *sql.DB
	var sn *Snapshot
	defer func() {
		e := retire(root, pool, nil)
		if sn != nil {
			e = errors.Join(e, sn.Close())
		}
		r.Cleanup = e == nil
		for _, sample := range r.Samples {
			r.Cleanup = r.Cleanup && sample.Cleanup
		}
		err = errors.Join(err, e)
	}()
	pool, e = root.Open(r.Route)
	if e != nil {
		return e
	}
	pool.SetMaxOpenConns(1)
	pool.SetMaxIdleConns(1)
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
	if e = oracle(ctx, pool); e != nil {
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
	at = time.Now()
	sn, e = root.Snapshot(ctx, r.Parallel)
	r.SnapshotMS = ms(time.Since(at))
	if e != nil {
		return e
	}
	if e = root.Close(); e != nil {
		return e
	}
	root = nil
	r.RootClosed = true
	jobs := make(chan int, r.Count)
	for i := 0; i < r.Count; i++ {
		jobs <- i
	}
	close(jobs)
	results := make(chan Sample, r.Count)
	var wg sync.WaitGroup
	if r.SyncDir != "" {
		if e = os.WriteFile(filepath.Join(r.SyncDir, "ready"), []byte("ready"), 0600); e != nil {
			return e
		}
		for {
			if _, e = os.Stat(filepath.Join(r.SyncDir, "go")); e == nil {
				break
			}
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(time.Millisecond):
			}
		}
	}
	var profile *os.File
	if path := os.Getenv("FORKSTAGES_CPU"); path != "" {
		profile, e = os.Create(path)
		if e != nil {
			return e
		}
		if e = pprof.StartCPUProfile(profile); e != nil {
			profile.Close()
			return e
		}
		defer profile.Close()
		defer pprof.StopCPUProfile()
	}
	var before, after syscall.Rusage
	if e = syscall.Getrusage(syscall.RUSAGE_SELF, &before); e != nil {
		return e
	}
	at = time.Now()
	for worker := 0; worker < r.Parallel; worker++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for index := range jobs {
				if ctx.Err() != nil {
					return
				}
				s, e := one(ctx, sn, r.Route, index, at)
				if e != nil {
					s.Error = e.Error()
					cancel()
				}
				results <- s
			}
		}()
	}
	wg.Wait()
	close(results)
	r.BatchMS = ms(time.Since(at))
	if e = syscall.Getrusage(syscall.RUSAGE_SELF, &after); e != nil {
		return e
	}
	r.CPUUserMS = float64(after.Utime.Nano()-before.Utime.Nano()) / 1e6
	r.CPUSystemMS = float64(after.Stime.Nano()-before.Stime.Nano()) / 1e6
	r.MinorFaults = after.Minflt - before.Minflt
	r.MajorFaults = after.Majflt - before.Majflt
	r.VoluntarySwitches = after.Nvcsw - before.Nvcsw
	r.InvoluntarySwitches = after.Nivcsw - before.Nivcsw
	r.LifetimeMaxRSSBytes = after.Maxrss
	if r.SyncDir != "" {
		if e = os.WriteFile(filepath.Join(r.SyncDir, "done"), []byte("done"), 0600); e != nil {
			return e
		}
	}
	for s := range results {
		r.Samples = append(r.Samples, s)
		if s.Error != "" {
			err = errors.Join(err, errors.New(s.Error))
		}
	}
	if err == nil && len(r.Samples) != r.Count {
		return fmt.Errorf("admitted=%d expected=%d", len(r.Samples), r.Count)
	}
	return err
}
func Main(backend string, start func(context.Context) (*Database, error)) {
	r := &Report{Backend: backend, Go: runtime.Version(), GOMAXPROCS: runtime.GOMAXPROCS(0)}
	flag.StringVar(&r.Route, "route", "tcp", "tcp or pipe")
	flag.IntVar(&r.Parallel, "parallel", 1, "maximum live child workers")
	flag.IntVar(&r.Count, "count", 20, "child count")
	flag.BoolVar(&r.Corrupt, "corrupt-seed", false, "negative control: child oracle must fail")
	out := flag.String("out", "", "required report path")
	flag.StringVar(&r.SyncDir, "sync-dir", "", "parent RSS observer handshake directory")
	flag.Parse()
	if *out == "" || r.Parallel < 1 || r.Count < r.Parallel || r.Parallel > 8 {
		fmt.Fprintln(os.Stderr, "invalid arguments")
		os.Exit(2)
	}
	e := run(r, start)
	r.Success = e == nil
	if e != nil {
		r.Error = e.Error()
	}
	raw, j := json.MarshalIndent(r, "", "  ")
	if j == nil {
		j = os.WriteFile(*out, append(raw, '\n'), 0600)
	}
	if j != nil {
		e = errors.Join(e, j)
	}
	if e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
