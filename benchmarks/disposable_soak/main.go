// Disposable lifecycle diagnostic. This changes no product runtime behavior.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"sync"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

type counters struct {
	RSS      uint64  `json:"rss_bytes"`
	Physical uint64  `json:"primary_bytes"`
	CPU      float64 `json:"cpu_seconds"`
}
type checkpoint struct {
	Counters     counters `json:"os"`
	HeapAlloc    uint64   `json:"heap_alloc_bytes"`
	HeapInuse    uint64   `json:"heap_inuse_bytes"`
	HeapIdle     uint64   `json:"heap_idle_bytes"`
	HeapReleased uint64   `json:"heap_released_bytes"`
	TotalAlloc   uint64   `json:"total_alloc_bytes"`
	Sys          uint64   `json:"sys_bytes"`
	NumGC        uint32   `json:"num_gc"`
	Goroutines   int      `json:"goroutines"`
	FDs          int      `json:"fds"`
}

func observe(helper string) (checkpoint, error) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	fdDir := "/dev/fd"
	if runtime.GOOS == "linux" {
		fdDir = "/proc/self/fd"
	}
	fds, err := os.ReadDir(fdDir)
	if err != nil {
		return checkpoint{}, err
	}
	pid := strconv.Itoa(os.Getpid())
	out, err := exec.Command(helper, pid).Output()
	if err != nil {
		return checkpoint{}, err
	}
	var values map[string]counters
	if err = json.Unmarshal(out, &values); err != nil {
		return checkpoint{}, err
	}
	c, ok := values[pid]
	if !ok || c.RSS == 0 || c.Physical == 0 {
		return checkpoint{}, errors.New("OS counters unavailable")
	}
	return checkpoint{c, m.HeapAlloc, m.HeapInuse, m.HeapIdle, m.HeapReleased, m.TotalAlloc, m.Sys, m.NumGC, runtime.NumGoroutine(), len(fds)}, nil
}

type generation struct {
	Generation   int        `json:"generation"`
	ReadySeconds float64    `json:"ready_seconds"`
	UseSeconds   float64    `json:"use_seconds"`
	CloseSeconds float64    `json:"close_seconds"`
	CPUSeconds   float64    `json:"cpu_seconds"`
	PerDBReady   []float64  `json:"per_db_ready_seconds"`
	Before       checkpoint `json:"before"`
	Ready        checkpoint `json:"ready"`
	AfterClose   checkpoint `json:"after_close"`
	Errors       []string   `json:"errors"`
}

func use(db *mariamem.Database) error {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	p, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	defer p.Close()
	for _, query := range []string{
		"CREATE TABLE disposable_rows(id INT PRIMARY KEY, value INT) ENGINE=InnoDB",
		"INSERT INTO disposable_rows VALUES(1,10)",
		"UPDATE disposable_rows SET value=11 WHERE id=1",
	} {
		if _, err = p.ExecContext(ctx, query); err != nil {
			return err
		}
	}
	tx, err := p.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	if _, err = tx.ExecContext(ctx, "UPDATE disposable_rows SET value=99 WHERE id=1"); err != nil {
		tx.Rollback()
		return err
	}
	if err = tx.Rollback(); err != nil {
		return err
	}
	var value int
	if err = p.QueryRowContext(ctx, "SELECT value FROM disposable_rows WHERE id=1").Scan(&value); err != nil {
		return err
	}
	if value != 11 {
		return fmt.Errorf("rollback/isolation value %d != 11", value)
	}
	_, err = p.ExecContext(ctx, "DELETE FROM disposable_rows WHERE id=1")
	return err
}
func run(helper string, number, n int) (generation, error) {
	g := generation{Generation: number, Errors: []string{}, PerDBReady: make([]float64, n)}
	before, err := observe(helper)
	if err != nil {
		return g, err
	}
	g.Before = before
	dbs := make([]*mariamem.Database, n)
	errs := make([]error, n)
	var wg sync.WaitGroup
	begin := time.Now()
	for i := range n {
		wg.Add(1)
		go func() {
			defer wg.Done()
			start := time.Now()
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()
			db, e := mariamem.Start(ctx, mariamem.Options{})
			dbs[i] = db
			if e == nil {
				var p *sql.DB
				p, e = sql.Open("mysql", db.DSN())
				if e == nil {
					var one int
					e = p.QueryRowContext(ctx, "SELECT 1").Scan(&one)
					if e == nil && one != 1 {
						e = fmt.Errorf("SELECT 1=%d", one)
					}
					e = errors.Join(e, p.Close())
				}
			}
			errs[i] = e
			g.PerDBReady[i] = time.Since(start).Seconds()
		}()
	}
	wg.Wait()
	g.ReadySeconds = time.Since(begin).Seconds()
	g.Ready, err = observe(helper)
	if err != nil {
		return g, err
	}
	begin = time.Now()
	for i := range n {
		if dbs[i] != nil && errs[i] == nil {
			wg.Add(1)
			go func() { defer wg.Done(); errs[i] = use(dbs[i]) }()
		}
	}
	wg.Wait()
	g.UseSeconds = time.Since(begin).Seconds()
	begin = time.Now()
	for i := range n {
		if dbs[i] != nil {
			wg.Add(1)
			go func() { defer wg.Done(); errs[i] = errors.Join(errs[i], dbs[i].Close()); dbs[i] = nil }()
		}
	}
	wg.Wait()
	g.CloseSeconds = time.Since(begin).Seconds()
	dbs = nil
	g.AfterClose, err = observe(helper)
	if err != nil {
		return g, err
	}
	g.CPUSeconds = g.AfterClose.Counters.CPU - g.Before.Counters.CPU
	for i, e := range errs {
		if e != nil {
			g.Errors = append(g.Errors, fmt.Sprintf("DB %d: %v", i, e))
		}
	}
	return g, nil
}
func main() {
	n := flag.Int("databases", 16, "concurrent isolated DBs per generation")
	count := flag.Int("generations", 50, "generations")
	helper := flag.String("cost-helper", "", "compiled benchmarks/tools/process_cost.c")
	output := flag.String("jsonl", "", "checkpoint evidence destination")
	flag.Parse()
	if *n < 1 || *count < 1 || *helper == "" || *output == "" {
		fmt.Fprintln(os.Stderr, "positive counts, cost-helper and jsonl required")
		os.Exit(2)
	}
	f, err := os.Create(*output)
	if err != nil {
		panic(err)
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	baseline, err := observe(*helper)
	if err != nil {
		panic(err)
	}
	enc.Encode(map[string]any{"type": "baseline", "runtime": "direct-linked generated-Go", "go_version": runtime.Version(), "os": runtime.GOOS, "arch": runtime.GOARCH, "databases": *n, "generations": *count, "checkpoint": baseline})
	excessCount, slowCount := 0, 0
	for i := 1; i <= *count; i++ {
		g, e := run(*helper, i, *n)
		if e != nil {
			g.Errors = append(g.Errors, e.Error())
		}
		enc.Encode(g)
		f.Sync()
		fmt.Printf("generation %d ready %.3fs close %.3fs CPU %.3fs heap %.1fMiB physical %.1fMiB FDs %d goroutines %d errors %d\n", i, g.ReadySeconds, g.CloseSeconds, g.CPUSeconds, float64(g.AfterClose.HeapAlloc)/(1<<20), float64(g.AfterClose.Counters.Physical)/(1<<20), g.AfterClose.FDs, g.AfterClose.Goroutines, len(g.Errors))
		if g.AfterClose.FDs > baseline.FDs+16 || g.AfterClose.Goroutines > baseline.Goroutines+64 {
			excessCount++
		} else {
			excessCount = 0
		}
		if g.ReadySeconds+g.UseSeconds+g.CloseSeconds >= 10 {
			slowCount++
		} else {
			slowCount = 0
		}
		reason := ""
		if len(g.Errors) > 0 {
			reason = "SQL/start/close/counter failure"
		} else if g.Ready.Counters.Physical > 12*(1<<30) || g.AfterClose.Counters.Physical > 12*(1<<30) {
			reason = "machine resource safety budget exceeded"
		} else if excessCount >= 3 {
			reason = "sustained FD/goroutine resource excess"
		} else if slowCount >= 3 {
			reason = "three consecutive >=10-second generations"
		}
		if reason != "" {
			enc.Encode(map[string]any{"type": "stop", "generation": i, "reason": reason})
			fmt.Fprintln(os.Stderr, reason)
			os.Exit(1)
		}
	}
	enc.Encode(map[string]any{"type": "completed", "generations": *count, "databases": *n})
}
