// Bounded serial Fork attribution. Built only with the recorded observation overlay.
package main

import (
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
	"sync"
	"syscall"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/timing"
)

type Event struct {
	Name   string `json:"name"`
	Offset int64  `json:"offset_ns"`
}
type Child struct {
	Ordinal   int             `json:"ordinal"`
	Wall      int64           `json:"fork_wall_ns"`
	CPU       int64           `json:"fork_cpu_ns"`
	Events    []Event         `json:"events"`
	Guest     json.RawMessage `json:"guest,omitempty"`
	SQLWall   int64           `json:"sql_wall_ns"`
	CloseWall int64           `json:"close_wall_ns"`
	Oracle    bool            `json:"oracle"`
	origin    time.Time
	reader    func() ([]byte, error)
}
type Result struct {
	Result   string            `json:"result"`
	Error    string            `json:"error,omitempty"`
	Traced   bool              `json:"traced"`
	Negative bool              `json:"negative"`
	Go       string            `json:"go"`
	GOOS     string            `json:"goos"`
	GOARCH   string            `json:"goarch"`
	Build    any               `json:"build"`
	Cap      int               `json:"cap"`
	Children []*Child          `json:"children"`
	Cleanup  map[string]uint64 `json:"cleanup"`
}

var mu sync.Mutex
var current *Child
var ctx = context.Background()

func cpu() int64 {
	var r syscall.Rusage
	if e := syscall.Getrusage(syscall.RUSAGE_SELF, &r); e != nil {
		panic(e)
	}
	return (r.Utime.Sec+r.Stime.Sec)*1e9 + int64(r.Utime.Usec+r.Stime.Usec)*1000
}
func pool(db *mariamem.Database) (*sql.DB, error) {
	p, e := sql.Open("mysql", db.DSN())
	if e == nil {
		p.SetMaxOpenConns(1)
		p.SetMaxIdleConns(1)
	}
	return p, e
}
func verify(p *sql.DB, sum int) error {
	var n, s int
	e := p.QueryRow("SELECT COUNT(*),SUM(v) FROM fork_probe").Scan(&n, &s)
	if e != nil {
		return e
	}
	if n != 1000 || s != sum {
		return fmt.Errorf("seed oracle: count=%d sum=%d expected=%d", n, s, sum)
	}
	return nil
}
func run(out *Result, traceDir string) (err error) {
	var reader func() ([]byte, error)
	timing.ForkObserver = func(name string, at time.Time) {
		mu.Lock()
		defer mu.Unlock()
		if current != nil {
			current.Events = append(current.Events, Event{name, at.Sub(current.origin).Nanoseconds()})
		}
	}
	generatedgo.ForkGuestTimingReader = func(f func() ([]byte, error)) { mu.Lock(); defer mu.Unlock(); reader = f }
	// The nil observer is the calibration path; the overlay is identical in both modes.
	if !out.Traced {
		timing.ForkObserver = nil
		generatedgo.ForkGuestTimingReader = nil
	}
	db, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		return e
	}
	defer func() { err = errors.Join(err, db.Close()) }()
	p, e := pool(db)
	if e != nil {
		return e
	}
	if _, e = p.Exec("CREATE TABLE fork_probe(id INTEGER PRIMARY KEY,v INTEGER NOT NULL) ENGINE=InnoDB"); e != nil {
		p.Close()
		return e
	}
	values := make([]string, 1000)
	for i := range values {
		values[i] = fmt.Sprintf("(%d,%d)", i+1, i+1)
	}
	_, e = p.Exec("INSERT INTO fork_probe VALUES " + strings.Join(values, ","))
	if e != nil {
		p.Close()
		return e
	}
	if e = verify(p, 500500); e != nil {
		p.Close()
		return e
	}
	if e = p.Close(); e != nil {
		return e
	}
	if e = db.WaitDisconnected(ctx); e != nil {
		return e
	}
	snap, e := db.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
	if e != nil {
		return e
	}
	defer func() { err = errors.Join(err, snap.Close()) }()
	out.Cap = snap.MaxForks()
	if out.Cap != 1 {
		return fmt.Errorf("unexpected cap: %d", out.Cap)
	}
	if e = db.Close(); e != nil {
		return e
	}
	if out.Traced {
		if e = os.Setenv("MARIAMEM_TIMING_DIR", traceDir); e != nil {
			return e
		}
	}
	for i := 0; i < 4; i++ {
		c := &Child{Ordinal: i, Events: []Event{}}
		mu.Lock()
		current = c
		reader = nil
		c.origin = time.Now()
		mu.Unlock()
		before := cpu()
		child, e := snap.Fork(ctx)
		c.Wall = time.Since(c.origin).Nanoseconds()
		c.CPU = cpu() - before
		mu.Lock()
		current = nil
		c.reader = reader
		mu.Unlock()
		out.Children = append(out.Children, c)
		if e != nil {
			return e
		}
		e = func() (err error) {
			defer func() {
				t := time.Now()
				err = errors.Join(err, child.Close())
				c.CloseWall = time.Since(t).Nanoseconds()
			}()
			if out.Traced {
				if c.reader == nil {
					return errors.New("missing guest timing reader")
				}
				b, e := c.reader()
				if e != nil {
					return e
				}
				if !json.Valid(b) {
					return errors.New("invalid guest timing")
				}
				c.Guest = b
				c.reader = nil
			}
			t := time.Now()
			p, e := pool(child)
			if e != nil {
				return e
			}
			defer func() { err = errors.Join(err, p.Close(), child.WaitDisconnected(ctx)) }()
			var one int
			if e = p.QueryRow("SELECT 1").Scan(&one); e != nil {
				return e
			}
			if one != 1 {
				return errors.New("SELECT1 oracle")
			}
			expected := 500500
			if out.Negative && i == 0 {
				expected++
			}
			if e = verify(p, expected); e != nil {
				return e
			}
			if _, e = p.Exec("UPDATE fork_probe SET v=v+1 WHERE id=1"); e != nil {
				return e
			}
			if e = verify(p, 500501); e != nil {
				return e
			}
			c.SQLWall = time.Since(t).Nanoseconds()
			c.Oracle = true
			return nil
		}()
		if e != nil {
			return e
		}
	}
	return nil
}
func main() {
	traced := flag.Bool("trace", false, "startup timing on")
	negative := flag.Bool("negative", false, "corrupt expected seed")
	dir := flag.String("trace-dir", "", "diagnostics directory")
	flag.Parse()
	_ = os.Unsetenv("MARIAMEM_TIMING_DIR")
	b, _ := debug.ReadBuildInfo()
	r := &Result{Result: "PASS", Traced: *traced, Negative: *negative, Go: runtime.Version(), GOOS: runtime.GOOS, GOARCH: runtime.GOARCH, Build: b}
	if e := run(r, *dir); e != nil {
		r.Result = "FAIL"
		r.Error = e.Error()
	}
	r.Cleanup = base.MemoryMappingStats()
	if r.Cleanup["active_mappings"] != 0 || r.Cleanup["active_rw_bytes"] != 0 || r.Cleanup["active_reserved_bytes"] != 0 {
		r.Result = "FAIL"
		r.Error += " mapping cleanup failed"
	}
	_ = json.NewEncoder(os.Stdout).Encode(r)
	if r.Result != "PASS" {
		os.Exit(1)
	}
}
