// Informational practical workflow comparison; no performance thresholds.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/timing"
	tc "github.com/testcontainers/testcontainers-go/modules/mariadb"
)

type observation struct {
	Latency   float64           `json:"latency_seconds"`
	Startup   float64           `json:"startup_seconds"`
	Fixture   float64           `json:"fixture_seconds"`
	ReadyAt   float64           `json:"ready_at_seconds"`
	Version   string            `json:"server_version"`
	Trace     *timing.Trace     `json:"host_trace,omitempty"`
	Caller    []timing.Event    `json:"caller_events"`
	Costs     map[string]any    `json:"ready_cost"`
	Settings  map[string]string `json:"server_settings"`
	pid       int
	container string
	pool      *sql.DB
	close     func() error
}

func fixture(ctx context.Context, p *sql.DB) error {
	if _, err := p.ExecContext(ctx, "CREATE TABLE benchmark_rows(id INT PRIMARY KEY, payload VARCHAR(64)) ENGINE=InnoDB"); err != nil {
		return err
	}
	tx, err := p.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	args := make([]any, 0, 2000)
	values := make([]string, 0, 1000)
	for i := 0; i < 1000; i++ {
		values = append(values, "(?,?)")
		args = append(args, i, strings.Repeat("x", 32))
	}
	if _, err = tx.ExecContext(ctx, "INSERT INTO benchmark_rows VALUES"+strings.Join(values, ","), args...); err != nil {
		return err
	}
	return tx.Commit()
}
func query(ctx context.Context, p *sql.DB, prepared bool) error {
	q, expected := "SELECT 1", 1
	if prepared {
		q, expected = "SELECT COUNT(*) FROM benchmark_rows", 1000
	}
	var got int
	if err := p.QueryRowContext(ctx, q).Scan(&got); err != nil {
		return err
	}
	if got != expected {
		return fmt.Errorf("first SQL returned %d, expected %d", got, expected)
	}
	return nil
}
func start(ctx context.Context, backend, scenario, native, image string, saved *mariamem.Snapshot, group time.Time) (o *observation, err error) {
	o = &observation{}
	begin := time.Now()
	o.Caller = []timing.Event{{Name: "begin", Offset: 0}}
	var dsn string
	if backend == "mariamem" {
		ctx = timing.WithRecorder(ctx, func(t timing.Trace) { o.Trace = &t; o.pid = t.RuntimePID })
		var db *mariamem.Database
		if scenario == "fixture" {
			db, err = saved.Fork(ctx)
		} else {
			db, err = mariamem.Start(ctx, mariamem.Options{NativeDir: native})
		}
		if err != nil {
			return nil, err
		}
		o.close = db.Close
		dsn = db.DSN()
	} else {
		var c *tc.MariaDBContainer
		c, err = tc.Run(ctx, image, tc.WithDatabase("test"), tc.WithUsername("root"), tc.WithPassword("benchmark-test-only"))
		if c != nil {
			o.container = c.GetContainerID()
			o.close = func() error {
				cleanup, cancel := context.WithTimeout(context.Background(), 60*time.Second)
				defer cancel()
				return c.Terminate(cleanup)
			}
		}
		if err != nil {
			if o.close != nil {
				err = errors.Join(err, o.close())
			}
			return nil, err
		}
		dsn, err = c.ConnectionString(ctx, "parseTime=true")
		if err != nil {
			_ = o.close()
			return nil, err
		}
	}
	owned := o
	defer func() {
		if err != nil {
			if owned.pool != nil {
				err = errors.Join(err, owned.pool.Close())
			}
			err = errors.Join(err, owned.close())
		}
	}()
	o.Caller = append(o.Caller, timing.Event{Name: "database_returned", Offset: time.Since(begin).Nanoseconds()})
	o.pool, err = sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}
	// Explicit connection readiness, identical driver for both backends.
	if err = o.pool.PingContext(ctx); err != nil {
		return nil, err
	}
	o.Startup = time.Since(begin).Seconds()
	o.Caller = append(o.Caller, timing.Event{Name: "client_connected", Offset: time.Since(begin).Nanoseconds()})
	if backend == "testcontainers" && scenario == "fixture" {
		f := time.Now()
		if err = fixture(ctx, o.pool); err != nil {
			return nil, err
		}
		o.Fixture = time.Since(f).Seconds()
	}
	if err = query(ctx, o.pool, scenario == "fixture"); err != nil {
		return nil, err
	}
	ready := time.Now()
	o.Caller = append(o.Caller, timing.Event{Name: "first_sql", Offset: ready.Sub(begin).Nanoseconds()})
	o.Latency = ready.Sub(begin).Seconds()
	o.ReadyAt = ready.Sub(group).Seconds()
	return o, nil
}
func cpuSelf() float64 {
	var u syscall.Rusage
	_ = syscall.Getrusage(syscall.RUSAGE_SELF, &u)
	return float64(u.Utime.Sec+u.Stime.Sec) + float64(u.Utime.Usec+u.Stime.Usec)/1e6
}
func costs(o *observation, hz float64) map[string]any {
	if o.container != "" {
		// Read actual Docker cgroup counters, not runner CPU or docker-stats CPU percent.
		client := &http.Client{Timeout: 15 * time.Second, Transport: &http.Transport{DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
			return (&net.Dialer{}).DialContext(ctx, "unix", "/var/run/docker.sock")
		}}}
		defer client.CloseIdleConnections()
		resp, err := client.Get("http://docker/containers/" + o.container + "/stats?stream=false&one-shot=true")
		if err != nil {
			return map[string]any{"error": err.Error()}
		}
		defer resp.Body.Close()
		if resp.StatusCode != 200 {
			return map[string]any{"error": resp.Status}
		}
		var s struct {
			CPU struct {
				Usage struct {
					Total uint64 `json:"total_usage"`
				} `json:"cpu_usage"`
			} `json:"cpu_stats"`
			Memory struct {
				Usage uint64            `json:"usage"`
				Stats map[string]uint64 `json:"stats"`
			} `json:"memory_stats"`
		}
		if err = json.NewDecoder(resp.Body).Decode(&s); err != nil {
			return map[string]any{"error": err.Error()}
		}
		if s.CPU.Usage.Total == 0 || s.Memory.Usage == 0 {
			return map[string]any{"error": "Docker one-shot accounting counters unavailable"}
		}
		return map[string]any{"mechanism": "Docker cgroup since container creation; includes entrypoint/init", "cpu_seconds": float64(s.CPU.Usage.Total) / 1e9, "memory_usage_bytes": s.Memory.Usage, "memory_stats": s.Memory.Stats}
	}
	b, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", o.pid))
	if err != nil {
		return map[string]any{"error": err.Error()}
	}
	fields := strings.Fields(string(b)[strings.LastIndex(string(b), ")")+2:])
	if len(fields) < 22 {
		return map[string]any{"error": "short /proc stat"}
	}
	u, e := strconv.ParseFloat(fields[11], 64)
	if e != nil {
		return map[string]any{"error": e.Error()}
	}
	st, e := strconv.ParseFloat(fields[12], 64)
	if e != nil {
		return map[string]any{"error": e.Error()}
	}
	rss, e := strconv.ParseInt(fields[21], 10, 64)
	if e != nil {
		return map[string]any{"error": e.Error()}
	}
	return map[string]any{"mechanism": "Wasmer process cumulative CPU and resident pages; excludes in-process Go host", "cpu_seconds": (u + st) / hz, "rss_bytes": rss * int64(os.Getpagesize())}
}
func batch(backend, scenario, native, image string, saved *mariamem.Snapshot, n int, hz float64) (out map[string]any, err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	all := make([]*observation, n)
	errs := make([]error, n)
	gate := make(chan struct{})
	var wg sync.WaitGroup
	begin := time.Now()
	cpu := cpuSelf()
	for i := range n {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-gate
			all[i], errs[i] = start(ctx, backend, scenario, native, image, saved, begin)
		}(i)
	}
	close(gate)
	wg.Wait()
	runnerCPU := cpuSelf() - cpu
	defer func() {
		for _, o := range all {
			if o != nil {
				err = errors.Join(err, o.pool.Close(), o.close())
			}
		}
	}()
	for _, e := range errs {
		err = errors.Join(err, e)
	}
	if err != nil {
		return nil, err
	}
	groupReady := 0.0
	for _, o := range all {
		groupReady = max(groupReady, o.ReadyAt)
	}
	// After ALL instances are ready: accounting/version collection cannot delay a peer's readiness.
	for _, o := range all {
		if err = o.pool.QueryRowContext(ctx, "SELECT VERSION()").Scan(&o.Version); err != nil {
			return nil, err
		}
		o.Costs = costs(o, hz)
		settings, e := o.pool.QueryContext(ctx, "SHOW VARIABLES WHERE Variable_name IN ('innodb_buffer_pool_size','key_buffer_size','aria_pagecache_buffer_size','innodb_flush_log_at_trx_commit','sync_binlog','skip_grant_tables')")
		if e != nil {
			return nil, e
		}
		o.Settings = map[string]string{}
		for settings.Next() {
			var name, value string
			if e = settings.Scan(&name, &value); e != nil {
				settings.Close()
				return nil, e
			}
			o.Settings[name] = value
		}
		e = errors.Join(settings.Err(), settings.Close())
		if e != nil {
			return nil, e
		}
		if scenario == "fixture" {
			var bytes, lo, hi int
			if err = o.pool.QueryRowContext(ctx, "SELECT SUM(CHAR_LENGTH(payload)), MIN(CHAR_LENGTH(payload)), MAX(CHAR_LENGTH(payload)) FROM benchmark_rows").Scan(&bytes, &lo, &hi); err != nil {
				return nil, err
			}
			if bytes != 32000 || lo != 32 || hi != 32 {
				return nil, errors.New("fixture payload identity mismatch")
			}
		}
		if backend == "mariamem" && (o.Trace == nil || len(o.Trace.Guest) == 0) {
			return nil, errors.New("missing lifecycle waterfall")
		}
	}
	return map[string]any{"backend": backend, "scenario": scenario, "workers": n, "group_ready_seconds": groupReady, "runner_cpu_seconds": runnerCPU, "per_db": all}, nil
}
func run() (err error) {
	native := flag.String("native-dir", "", "verified canonical native dir")
	image := flag.String("image", "", "digest-pinned pre-pulled image")
	output := flag.String("json", "", "result path")
	runs := flag.Int("runs", 20, "measured rounds")
	warmup := flag.Int("warmup", 2, "warmup rounds")
	flag.Parse()
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		return errors.New("comparison requires Ubuntu 24.04 x86_64")
	}
	if *runs < 1 || *warmup < 0 || *native == "" || *output == "" || !strings.Contains(*image, "@sha256:") {
		return errors.New("native dir, output, digest-pinned image and valid run counts required")
	}
	dir, err := os.MkdirTemp("", "mariamem-competitive-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(dir)
	if err = os.Setenv("MARIAMEM_TIMING_DIR", filepath.Join(dir, "timing")); err != nil {
		return err
	}
	if err = os.MkdirAll(os.Getenv("MARIAMEM_TIMING_DIR"), 0700); err != nil {
		return err
	}
	tick, err := exec.Command("getconf", "CLK_TCK").Output()
	if err != nil {
		return err
	}
	hz, err := strconv.ParseFloat(strings.TrimSpace(string(tick)), 64)
	if err != nil || hz <= 0 {
		return errors.New("cannot determine CPU clock ticks")
	}
	source, err := exec.Command("git", "rev-parse", "HEAD").Output()
	if err != nil {
		return err
	}
	report := map[string]any{"schema_version": 1, "completed": false, "source_commit": strings.TrimSpace(string(source)), "go": runtime.Version(), "cpus": runtime.NumCPU(), "image": *image, "runs": *runs, "warmup": *warmup, "rows": 1000, "payload_characters": 32, "samples": []map[string]any{}}
	defer func() {
		if err != nil {
			report["error"] = err.Error()
		}
		if e := os.MkdirAll(filepath.Dir(*output), 0755); e != nil {
			err = errors.Join(err, e)
			return
		}
		b, e := json.MarshalIndent(report, "", "  ")
		if e == nil {
			e = os.WriteFile(*output, append(b, '\n'), 0644)
		}
		err = errors.Join(err, e)
	}()
	prep := time.Now()
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{NativeDir: *native})
	if err != nil {
		return err
	}
	defer db.Close()
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	err = fixture(ctx, pool)
	err = errors.Join(err, pool.Close())
	if err != nil {
		return err
	}
	if err = db.WaitDisconnected(ctx); err != nil {
		return err
	}
	saved, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, saved.Close()) }()
	report["prepared_snapshot_setup_seconds"] = time.Since(prep).Seconds()
	samples := []map[string]any{}
	for _, scenario := range []string{"empty", "fixture"} {
		for _, n := range []int{1, 4, 8} {
			for round := 0; round < *warmup+*runs; round++ {
				order := []string{"mariamem", "testcontainers"}
				if round%2 == 1 {
					order[0], order[1] = order[1], order[0]
				}
				for position, backend := range order {
					row, e := batch(backend, scenario, *native, *image, saved, n, hz)
					if e != nil {
						return fmt.Errorf("%s %s x%d round %d: %w", backend, scenario, n, round, e)
					}
					row["round"] = round
					row["position"] = position
					row["phase"] = "measurement"
					if round < *warmup {
						row["phase"] = "warmup"
					}
					samples = append(samples, row)
					report["samples"] = samples
				}
			}
		}
	}
	report["completed"] = true
	return nil
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
