// Bounded product comparison. No generated-code overlays or diagnostic hooks.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"sync"
	"syscall"
	"time"
)

type Sample struct {
	Index                              int `json:"index"`
	Startup, Seed, SQL, Cleanup, Total float64
	Error                              string `json:"error,omitempty"`
}
type Report struct {
	Route                                   string
	Parallel, Count                         int
	Samples                                 []Sample
	Setup, Batch, Suite, BatchCPU, SuiteCPU float64
	Cleanup                                 map[string]uint64
	Success                                 bool
	Error                                   string `json:"error,omitempty"`
}

func ms(t time.Time) float64 { return float64(time.Since(t)) / 1e6 }
func cpu() float64 {
	var r syscall.Rusage
	if err := syscall.Getrusage(syscall.RUSAGE_SELF, &r); err != nil {
		panic(err)
	}
	return float64(r.Utime.Sec+r.Stime.Sec)*1000 + float64(r.Utime.Usec+r.Stime.Usec)/1000
}
func pool(db *mariamem.Database) (*sql.DB, error) {
	c, e := mysql.ParseDSN(db.DSN())
	if e != nil {
		return nil, e
	}
	c.DialFunc = db.DialContext
	c.InterpolateParams = false
	conn, e := mysql.NewConnector(c)
	if e != nil {
		return nil, e
	}
	p := sql.OpenDB(conn)
	p.SetMaxOpenConns(1)
	return p, nil
}
func seed(ctx context.Context, p *sql.DB) error {
	for _, q := range []string{"CREATE TABLE fixture(id INT PRIMARY KEY, value INT)", "INSERT INTO fixture VALUES(1,10),(2,20)"} {
		if _, e := p.ExecContext(ctx, q); e != nil {
			return e
		}
	}
	return nil
}
func check(ctx context.Context, p *sql.DB, want int) error {
	var n, s int
	if e := p.QueryRowContext(ctx, "SELECT COUNT(*),SUM(value) FROM fixture").Scan(&n, &s); e != nil {
		return e
	}
	if n != 2 || s != want {
		return fmt.Errorf("pristine oracle: count=%d sum=%d want=%d", n, s, want)
	}
	return nil
}
func child(ctx context.Context, snap *mariamem.Snapshot, route string, index, want int) (r Sample) {
	r.Index = index
	begin := time.Now()
	var db *mariamem.Database
	var p *sql.DB
	var err error
	defer func() {
		at := time.Now()
		if p != nil {
			err = errors.Join(err, p.Close())
		}
		if db != nil {
			err = errors.Join(err, db.WaitDisconnected(ctx), db.Close())
		}
		r.Cleanup = ms(at)
		r.Total = ms(begin)
		if err != nil {
			r.Error = err.Error()
		}
	}()
	at := time.Now()
	if route == "fork" {
		db, err = snap.Fork(ctx)
	} else {
		db, err = mariamem.Start(ctx, mariamem.Options{})
	}
	r.Startup = ms(at)
	if err != nil {
		return
	}
	p, err = pool(db)
	if err != nil {
		return
	}
	if route == "fresh" {
		at = time.Now()
		err = seed(ctx, p)
		r.Seed = ms(at)
		if err != nil {
			return
		}
	}
	at = time.Now()
	err = check(ctx, p, want)
	if err != nil {
		return
	}
	_, err = p.ExecContext(ctx, "UPDATE fixture SET value=? WHERE id=1", 99)
	if err != nil {
		return
	}
	err = check(ctx, p, 119)
	if err != nil {
		return
	}
	var one int
	err = p.QueryRowContext(ctx, "SELECT 1").Scan(&one)
	if err == nil && one != 1 {
		err = fmt.Errorf("subsequent SELECT: %d", one)
	}
	r.SQL = ms(at)
	return
}
func run(route string, parallel, count, want int) (r Report) {
	r.Route = route
	r.Parallel = parallel
	r.Count = count
	r.Samples = make([]Sample, count)
	begin := time.Now()
	startCPU := cpu()
	var err error
	var db *mariamem.Database
	var p *sql.DB
	var snap *mariamem.Snapshot
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	defer func() {
		if p != nil {
			err = errors.Join(err, p.Close())
		}
		if db != nil {
			err = errors.Join(err, db.WaitDisconnected(ctx), db.Close())
		}
		if snap != nil {
			err = errors.Join(err, snap.Close())
		}
		r.Suite = ms(begin)
		r.SuiteCPU = cpu() - startCPU
		r.Cleanup = base.MemoryMappingStats()
		for _, key := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes", "release_failures", "grow_failures"} {
			if r.Cleanup[key] != 0 {
				err = errors.Join(err, fmt.Errorf("cleanup %s=%d", key, r.Cleanup[key]))
			}
		}
		r.Success = err == nil
		if err != nil {
			r.Error = err.Error()
		}
	}()
	db, err = mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		return
	}
	p, err = pool(db)
	if err != nil {
		return
	}
	err = seed(ctx, p)
	if err != nil {
		return
	}
	err = p.Close()
	p = nil
	if err != nil {
		return
	}
	err = db.WaitDisconnected(ctx)
	if err != nil {
		return
	}
	snap, err = db.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: parallel})
	if err != nil {
		return
	}
	db = nil
	r.Setup = ms(begin)
	batch := time.Now()
	batchCPU := cpu()
	for first := 0; first < count; first += parallel {
		var ready, done sync.WaitGroup
		ready.Add(parallel)
		done.Add(parallel)
		gate := make(chan struct{})
		for j := 0; j < parallel; j++ {
			i := first + j
			go func() { defer done.Done(); ready.Done(); <-gate; r.Samples[i] = child(ctx, snap, route, i, want) }()
		}
		ready.Wait()
		close(gate)
		done.Wait()
		for _, v := range r.Samples[first : first+parallel] {
			if v.Error != "" {
				err = errors.Join(err, fmt.Errorf("child %d: %s", v.Index, v.Error))
			}
		}
		if err != nil {
			break
		}
	}
	r.Batch = ms(batch)
	r.BatchCPU = cpu() - batchCPU
	return
}
func main() {
	route := flag.String("route", "fork", "fresh/fork")
	parallel := flag.Int("parallel", 1, "fixed wave width")
	count := flag.Int("count", 48, "children")
	want := flag.Int("expected-sum", 30, "negative oracle control")
	flag.Parse()
	if (*route != "fresh" && *route != "fork") || (*parallel != 1 && *parallel != 4) || *count <= 0 || *count%*parallel != 0 {
		panic("invalid bounded input")
	}
	r := run(*route, *parallel, *count, *want)
	if e := json.NewEncoder(os.Stdout).Encode(r); e != nil {
		panic(e)
	}
	if !r.Success {
		os.Exit(1)
	}
}
