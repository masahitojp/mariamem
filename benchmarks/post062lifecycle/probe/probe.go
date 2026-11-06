// Package probe measures complete Fresh/Fork suites with identical SQL oracles.
package probe

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"runtime"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
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
	MaxForks int

	Fork  func(context.Context) (*Database, error)
	Close func() error
}
type Span struct {
	Name  string  `json:"name"`
	Begin float64 `json:"begin_ms"`
	End   float64 `json:"end_ms"`
}
type Sample struct {
	Index   int     `json:"index"`
	Lane    int     `json:"lane"`
	Begin   float64 `json:"begin_ms"`
	End     float64 `json:"end_ms"`
	Spans   []Span  `json:"spans"`
	Oracle  bool    `json:"oracle"`
	Cleanup bool    `json:"cleanup"`
	Error   string  `json:"error,omitempty"`
	Version string  `json:"version,omitempty"`
}
type Report struct {
	ResolvedMaxForks int `json:"resolved_max_forks"`

	Backend      string            `json:"backend"`
	Mode         string            `json:"mode"`
	Parallel     int               `json:"parallel"`
	Count        int               `json:"count"`
	Corrupt      bool              `json:"corrupt_seed"`
	Go           string            `json:"go"`
	GOMAXPROCS   int               `json:"gomaxprocs"`
	Suite        float64           `json:"suite_ms"`
	CPU          float64           `json:"suite_cpu_ms"`
	BatchBegin   float64           `json:"batch_begin_ms"`
	BatchEnd     float64           `json:"batch_end_ms"`
	Batch        float64           `json:"batch_ms"`
	BatchCPU     float64           `json:"batch_cpu_ms"`
	MaxRSS       int64             `json:"lifetime_max_rss_bytes"`
	Root         []Span            `json:"root_spans"`
	Samples      []Sample          `json:"samples"`
	MaxActive    int32             `json:"max_active"`
	Cleanup      bool              `json:"cleanup"`
	CleanupStats map[string]uint64 `json:"cleanup_stats,omitempty"`
	Success      bool              `json:"success"`
	Error        string            `json:"error,omitempty"`
	origin       time.Time
}

var CleanupStats func() map[string]uint64

func clock() syscall.Rusage {
	var r syscall.Rusage
	if e := syscall.Getrusage(syscall.RUSAGE_SELF, &r); e != nil {
		panic(e)
	}
	return r
}
func cpu(r syscall.Rusage) int64 { return r.Utime.Nano() + r.Stime.Nano() }
func ms(t time.Duration) float64 { return float64(t) / 1e6 }
func measured(spans *[]Span, origin time.Time, name string, f func() error) error {
	at := ms(time.Since(origin))
	e := f()
	*spans = append(*spans, Span{name, at, ms(time.Since(origin))})
	return e
}
func connect(ctx context.Context, d *Database) (p *sql.DB, c *sql.Conn, err error) {
	p, err = d.Open("pipe")
	if err != nil {
		return
	}
	p.SetMaxOpenConns(1)
	p.SetMaxIdleConns(1)
	c, err = p.Conn(ctx)
	return
}
func retire(d *Database, p *sql.DB, c *sql.Conn) error {
	var e error
	if c != nil {
		e = errors.Join(e, c.Close())
	}
	if p != nil {
		e = errors.Join(e, p.Close())
	}
	if d != nil && d.Wait != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		e = errors.Join(e, d.Wait(ctx))
	}
	return e
}
func oracle(ctx context.Context, c *sql.Conn) error {
	var n, s int
	if e := c.QueryRowContext(ctx, "SELECT COUNT(*),SUM(v) FROM fork_probe").Scan(&n, &s); e != nil {
		return e
	}
	if n != 1000 || s != 500500 {
		return fmt.Errorf("pristine oracle: count=%d sum=%d", n, s)
	}
	return nil
}
func seed(ctx context.Context, c *sql.Conn, corrupt bool) error {
	if _, e := c.ExecContext(ctx, "CREATE TABLE fork_probe(id INTEGER PRIMARY KEY,v INTEGER NOT NULL)"); e != nil {
		return e
	}
	values := make([]string, 1000)
	for i := range values {
		values[i] = fmt.Sprintf("(%d,%d)", i+1, i+1)
	}
	if _, e := c.ExecContext(ctx, "INSERT INTO fork_probe VALUES "+strings.Join(values, ",")); e != nil {
		return e
	}
	if e := oracle(ctx, c); e != nil {
		return e
	}
	if corrupt {
		_, e := c.ExecContext(ctx, "UPDATE fork_probe SET v=-1 WHERE id=1")
		return e
	}
	return nil
}
func one(ctx context.Context, r *Report, lane, index int, start func(context.Context) (*Database, error), sn *Snapshot) (s Sample, err error) {
	ctx = context.WithValue(ctx, "forkstages_child", index)
	s = Sample{Index: index, Lane: lane, Begin: ms(time.Since(r.origin)), Spans: []Span{}, Cleanup: true}
	var d *Database
	var p *sql.DB
	var c *sql.Conn
	defer func() {
		e := measured(&s.Spans, r.origin, "retire", func() error { return retire(d, p, c) })
		if d != nil {
			e = errors.Join(e, measured(&s.Spans, r.origin, "close", d.Close))
		}
		s.Cleanup = e == nil
		err = errors.Join(err, e)
		s.End = ms(time.Since(r.origin))
		if err != nil {
			s.Error = err.Error()
		}
	}()
	if err = measured(&s.Spans, r.origin, "start_or_fork", func() error {
		var e error
		if sn != nil {
			d, e = sn.Fork(ctx)
		} else {
			d, e = start(ctx)
		}
		return e
	}); err != nil {
		return
	}
	if err = measured(&s.Spans, r.origin, "connect", func() error { var e error; p, c, e = connect(ctx, d); return e }); err != nil {
		return
	}
	if index == 0 {
		if err = measured(&s.Spans, r.origin, "version", func() error { return c.QueryRowContext(ctx, "SELECT VERSION()").Scan(&s.Version) }); err != nil {
			return
		}
	}
	if err = measured(&s.Spans, r.origin, "select1", func() error {
		var n int
		if e := c.QueryRowContext(ctx, "SELECT 1").Scan(&n); e != nil {
			return e
		}
		if n != 1 {
			return fmt.Errorf("SELECT1=%d", n)
		}
		return nil
	}); err != nil {
		return
	}
	if r.Mode == "fresh" {
		if err = measured(&s.Spans, r.origin, "seed", func() error { return seed(ctx, c, r.Corrupt && index == 0) }); err != nil {
			return
		}
	}
	if err = measured(&s.Spans, r.origin, "count_sum", func() error { return oracle(ctx, c) }); err != nil {
		return
	}
	if err = measured(&s.Spans, r.origin, "update", func() error {
		result, e := c.ExecContext(ctx, "UPDATE fork_probe SET v=-1 WHERE id=1")
		if e != nil {
			return e
		}
		n, e := result.RowsAffected()
		if e != nil {
			return e
		}
		if n != 1 {
			return fmt.Errorf("affected=%d", n)
		}
		return nil
	}); err != nil {
		return
	}
	if err = measured(&s.Spans, r.origin, "verify_update", func() error {
		var v int
		if e := c.QueryRowContext(ctx, "SELECT v FROM fork_probe WHERE id=1").Scan(&v); e != nil {
			return e
		}
		if v != -1 {
			return fmt.Errorf("updated=%d", v)
		}
		return nil
	}); err != nil {
		return
	}
	s.Oracle = true
	return
}
func run(r *Report, start func(context.Context) (*Database, error)) (err error) {
	r.origin = time.Now()
	before := clock()
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	var root *Database
	var p *sql.DB
	var c *sql.Conn
	var sn *Snapshot
	defer func() {
		e := measured(&r.Root, r.origin, "final_root_retire", func() error { return retire(root, p, c) })
		if root != nil {
			e = errors.Join(e, measured(&r.Root, r.origin, "final_root_close", root.Close))
		}
		if sn != nil {
			e = errors.Join(e, measured(&r.Root, r.origin, "snapshot_close", sn.Close))
		}
		err = errors.Join(err, e)
		r.Cleanup = e == nil
		for _, s := range r.Samples {
			r.Cleanup = r.Cleanup && s.Cleanup
		}
		if CleanupStats != nil {
			r.CleanupStats = CleanupStats()
			for _, k := range []string{"active_mappings", "active_rw_bytes", "active_reserved_bytes", "release_failures"} {
				if r.CleanupStats[k] != 0 {
					r.Cleanup = false
					err = errors.Join(err, fmt.Errorf("mapping cleanup: %s=%d", k, r.CleanupStats[k]))
				}
			}
		}
		r.Suite = ms(time.Since(r.origin))
		after := clock()
		r.CPU = float64(cpu(after)-cpu(before)) / 1e6
		r.MaxRSS = after.Maxrss
	}()
	if r.Mode == "fork" {
		if err = measured(&r.Root, r.origin, "root_start", func() error { var e error; root, e = start(ctx); return e }); err != nil {
			return
		}
		if err = measured(&r.Root, r.origin, "root_connect", func() error { var e error; p, c, e = connect(ctx, root); return e }); err != nil {
			return
		}
		if err = measured(&r.Root, r.origin, "root_seed", func() error { return seed(ctx, c, r.Corrupt) }); err != nil {
			return
		}
		if err = measured(&r.Root, r.origin, "root_retire", func() error { return retire(root, p, c) }); err != nil {
			return
		}
		p = nil
		c = nil
		if err = measured(&r.Root, r.origin, "snapshot", func() error { var e error; sn, e = root.Snapshot(ctx, r.Parallel); return e }); err != nil {
			return
		}
		r.ResolvedMaxForks = sn.MaxForks
		if r.ResolvedMaxForks != r.Parallel {
			return fmt.Errorf("resolved cap=%d expected=%d", r.ResolvedMaxForks, r.Parallel)
		}
		if err = measured(&r.Root, r.origin, "root_close", root.Close); err != nil {
			return
		}
		root = nil
	}
	jobs := make(chan int, r.Count)
	for i := 0; i < r.Count; i++ {
		jobs <- i
	}
	close(jobs)
	results := make(chan Sample, r.Count)
	var wg sync.WaitGroup
	var active atomic.Int32
	var peak atomic.Int32
	at := time.Now()
	r.BatchBegin = ms(at.Sub(r.origin))
	batchCPU := clock()
	for lane := 0; lane < r.Parallel; lane++ {
		wg.Add(1)
		go func(lane int) {
			defer wg.Done()
			for index := range jobs {
				if ctx.Err() != nil {
					return
				}
				n := active.Add(1)
				for old := peak.Load(); n > old; old = peak.Load() {
					if peak.CompareAndSwap(old, n) {
						break
					}
				}
				s, e := one(ctx, r, lane, index, start, sn)
				active.Add(-1)
				if e != nil {
					cancel()
				}
				results <- s
			}
		}(lane)
	}
	wg.Wait()
	close(results)
	r.BatchEnd = ms(time.Since(r.origin))
	r.Batch = r.BatchEnd - r.BatchBegin
	r.BatchCPU = float64(cpu(clock())-cpu(batchCPU)) / 1e6
	r.MaxActive = peak.Load()
	for s := range results {
		r.Samples = append(r.Samples, s)
		if s.Error != "" {
			err = errors.Join(err, errors.New(s.Error))
		}
	}
	sort.Slice(r.Samples, func(i, j int) bool { return r.Samples[i].Index < r.Samples[j].Index })
	if err == nil && len(r.Samples) != r.Count {
		err = fmt.Errorf("completed=%d expected=%d", len(r.Samples), r.Count)
	}
	return
}
func Main(backend string, start func(context.Context) (*Database, error)) {
	r := &Report{Backend: backend, Go: runtime.Version(), GOMAXPROCS: runtime.GOMAXPROCS(0), Root: []Span{}, Samples: []Sample{}}
	flag.StringVar(&r.Mode, "mode", "fork", "fresh or fork")
	flag.IntVar(&r.Parallel, "parallel", 1, "bounded worker count")
	flag.IntVar(&r.Count, "count", 48, "isolated cases")
	flag.BoolVar(&r.Corrupt, "corrupt-seed", false, "negative oracle")
	out := flag.String("out", "", "JSON result")
	flag.Parse()
	if *out == "" || (r.Mode != "fresh" && r.Mode != "fork") || r.Parallel < 1 || r.Parallel > 8 || r.Count < r.Parallel {
		fmt.Fprintln(os.Stderr, "invalid arguments")
		os.Exit(2)
	}
	e := run(r, start)
	r.Success = e == nil
	if e != nil {
		r.Error = e.Error()
	}
	b, j := json.MarshalIndent(r, "", "  ")
	if j == nil {
		j = os.WriteFile(*out, append(b, '\n'), 0600)
	}
	if e != nil || j != nil {
		fmt.Fprintln(os.Stderr, errors.Join(e, j))
		os.Exit(1)
	}
}
