// Repeated-suite comparison only; no production configuration changes.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"runtime/debug"
	"strconv"
	"strings"
	"syscall"
	"time"

	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func clockSeconds(raw string) (float64, error) {
	total := 0.0
	for _, p := range strings.Split(raw, ":") {
		v, e := strconv.ParseFloat(p, 64)
		if e != nil {
			return 0, e
		}
		total = total*60 + v
	}
	return total, nil
}
func runtimePID() (int, error) {
	b, e := exec.Command("ps", "-axo", "pid=,ppid=,comm=").Output()
	if e != nil {
		return 0, e
	}
	for _, line := range strings.Split(string(b), "\n") {
		f := strings.Fields(line)
		if len(f) >= 3 && f[1] == strconv.Itoa(os.Getpid()) && strings.Contains(strings.Join(f[2:], " "), "wasmer") {
			return strconv.Atoi(f[0])
		}
	}
	return 0, errors.New("Wasmer child not observable")
}
func verifyAndMutate(ctx context.Context, p *sql.DB) error {
	var count, chars int
	if e := p.QueryRowContext(ctx, "SELECT COUNT(*), SUM(CHAR_LENGTH(payload)) FROM benchmark_rows").Scan(&count, &chars); e != nil {
		return e
	}
	if count != 1000 || chars != 32000 {
		return errors.New("fixture identity mismatch")
	}
	var payload string
	if e := p.QueryRowContext(ctx, "SELECT payload FROM benchmark_rows WHERE id=0").Scan(&payload); e != nil {
		return e
	}
	if payload != strings.Repeat("x", 32) {
		return errors.New("previous test mutation leaked")
	}
	_, e := p.ExecContext(ctx, "UPDATE benchmark_rows SET payload='isolated-test-mutation' WHERE id=0")
	return e
}
func runSuite(mode string, count int, native, image, output string) (err error) {
	if mode != "mariamem-fresh" && mode != "mariamem-prepared" && mode != "testcontainers-fresh" && mode != "testcontainers-schema-reset" {
		return errors.New("unknown suite mode")
	}
	if count < 1 || output == "" {
		return errors.New("positive suite count and output required")
	}
	if runtime.GOOS != "darwin" && runtime.GOOS != "linux" {
		return errors.New("unsupported benchmark platform")
	}
	for _, key := range []string{"MARIAMEM_TIMING_DIR", "MARIAMEM_INIT_DIAGNOSTICS", "MARIAMEM_MEMORY_DIAGNOSTICS"} {
		os.Unsetenv(key)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Minute)
	defer cancel()
	source, e := exec.Command("git", "rev-parse", "HEAD").Output()
	if e != nil {
		return e
	}
	info, _ := debug.ReadBuildInfo()
	report := map[string]any{"schema_version": 1, "mode": mode, "tests": count, "completed": false, "source_commit": strings.TrimSpace(string(source)), "go_build_info": info, "samples": []map[string]any{}}
	persist := func() {
		b, _ := json.MarshalIndent(report, "", "  ")
		_ = os.MkdirAll(filepath.Dir(output), 0755)
		_ = os.WriteFile(output, append(b, '\n'), 0600)
	}
	defer func() {
		if err != nil {
			report["error"] = err.Error()
		}
		persist()
	}()
	backend := "mariamem"
	if strings.HasPrefix(mode, "testcontainers") {
		backend = "testcontainers"
	}
	var snapshot *mariamem.Snapshot
	var shared *observation
	var admin *sql.DB
	begin := time.Now()
	self := cpuSelf()
	var childrenBefore syscall.Rusage
	syscall.Getrusage(syscall.RUSAGE_CHILDREN, &childrenBefore)
	setup := map[string]float64{}
	// Prepared lower state belongs to the suite and is NOT free amortized setup.
	if mode == "mariamem-prepared" || mode == "testcontainers-schema-reset" {
		t := time.Now()
		o, e := start(ctx, backend, "empty", native, image, nil, t)
		if e != nil {
			return e
		}
		setup["first_sql_seconds"] = o.Latency
		report["server_version"] = version(ctx, o.pool)
		if mode == "mariamem-prepared" {
			db := o.db
			pool := o.pool
			t = time.Now()
			e = fixture(ctx, pool)
			setup["migration_fixture_seconds"] = time.Since(t).Seconds()
			e = errors.Join(e, pool.Close())
			if e != nil {
				db.Close()
				return e
			}
			if e = db.WaitDisconnected(ctx); e != nil {
				db.Close()
				return e
			}
			t = time.Now()
			snapshot, e = db.Snapshot(ctx, mariamem.SnapshotOptions{})
			setup["snapshot_seconds"] = time.Since(t).Seconds()
			if e != nil {
				db.Close()
				return e
			}
			defer func() {
				if snapshot != nil {
					err = errors.Join(err, snapshot.Close())
				}
			}()
		} else {
			shared = o
			defer func() {
				if shared != nil {
					err = errors.Join(err, shared.pool.Close(), shared.close())
				}
			}()
			// Admin pool has no selected database; each test gets a new schema and pool.
			dsn, e := mysql.ParseDSN(shared.dsn)
			if e != nil {
				return e
			}
			dsn.DBName = ""
			admin, e = sql.Open("mysql", dsn.FormatDSN())
			if e != nil {
				return e
			}
			defer admin.Close()
		}
	}
	report["setup"] = setup
	report["setup_wall_seconds"] = time.Since(begin).Seconds()
	samples := []map[string]any{}
	var active *observation
	defer func() {
		if active != nil {
			err = errors.Join(err, active.pool.Close(), active.close())
		}
	}()
	for i := 0; i < count; i++ {
		t := time.Now()
		row := map[string]any{"test": i}
		var o *observation
		if mode == "testcontainers-schema-reset" {
			f := time.Now()
			if _, e = admin.ExecContext(ctx, "DROP DATABASE IF EXISTS benchmark_case"); e != nil {
				return e
			}
			if _, e = admin.ExecContext(ctx, "CREATE DATABASE benchmark_case"); e != nil {
				return e
			}
			config, e := mysql.ParseDSN(shared.dsn)
			if e != nil {
				return e
			}
			config.DBName = "benchmark_case"
			pool, e := sql.Open("mysql", config.FormatDSN())
			if e != nil {
				return e
			}
			o = &observation{pool: pool, container: shared.container, close: func() error { return nil }}
			if e = fixture(ctx, pool); e != nil {
				pool.Close()
				return e
			}
			row["schema_reset_migration_fixture_seconds"] = time.Since(f).Seconds()

		} else {
			scenario := "empty"
			if snapshot != nil {
				scenario = "fixture"
			}
			o, e = start(ctx, backend, scenario, native, image, snapshot, t)
			if e != nil {
				return e
			}
			row["startup_first_sql_seconds"] = o.Latency
			if snapshot == nil {
				f := time.Now()
				e = fixture(ctx, o.pool)
				row["migration_fixture_seconds"] = time.Since(f).Seconds()
				if e != nil {
					o.pool.Close()
					o.close()
					return e
				}
			}
		}
		active = o
		if e = query(ctx, o.pool, true); e != nil {
			o.pool.Close()
			o.close()
			return e
		}
		row["fixture_ready_seconds"] = time.Since(t).Seconds()
		if o.container != "" {
			row["container_id"] = o.container
		}
		q := time.Now()
		e = verifyAndMutate(ctx, o.pool)
		row["test_sql_seconds"] = time.Since(q).Seconds()
		if e != nil {
			o.pool.Close()
			o.close()
			return e
		}
		if report["server_version"] == nil {
			report["server_version"] = version(ctx, o.pool)
		}
		if report["server_settings"] == nil {
			rows, e := o.pool.QueryContext(ctx, "SHOW VARIABLES WHERE Variable_name IN ('innodb_buffer_pool_size','key_buffer_size','aria_pagecache_buffer_size','innodb_flush_log_at_trx_commit','sync_binlog','skip_grant_tables')")
			if e != nil {
				return e
			}
			settings := map[string]string{}
			for rows.Next() {
				var name, value string
				if e = rows.Scan(&name, &value); e != nil {
					rows.Close()
					return e
				}
				settings[name] = value
			}
			e = errors.Join(rows.Err(), rows.Close())
			if e != nil {
				return e
			}
			report["server_settings"] = settings
		}
		if i == 0 || i == count-1 || mode == "testcontainers-fresh" {
			observer := time.Now()
			if backend == "mariamem" {
				o.pid, e = runtimePID()
				if e != nil {
					return e
				}
			}
			cost := costs(o, 100)
			if o.container != "" {
				peakCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
				raw, peakErr := exec.CommandContext(peakCtx, "docker", "exec", o.container, "cat", "/sys/fs/cgroup/memory.peak").Output()
				cancel()
				if peakErr == nil {
					peak, e := strconv.ParseUint(strings.TrimSpace(string(raw)), 10, 64)
					if e == nil {
						cost["cgroup_v2_memory_peak_bytes"] = peak
					} else {
						cost["peak_memory_error"] = e.Error()
					}
				} else {
					cost["peak_memory_error"] = peakErr.Error()
				}
			}
			row["ready_cost"] = cost
			row["resource_observation_seconds"] = time.Since(observer).Seconds()

		}
		closeAt := time.Now()
		e = errors.Join(o.pool.Close(), o.close())
		active = nil
		row["cleanup_seconds"] = time.Since(closeAt).Seconds()
		if e != nil {
			return e
		}
		row["observed_test_wall_seconds"] = time.Since(t).Seconds()
		samples = append(samples, row)
		report["samples"] = samples
		persist()
	}
	if snapshot != nil {
		t := time.Now()
		err = snapshot.Close()
		snapshot = nil
		report["suite_cleanup_seconds"] = time.Since(t).Seconds()
		if err != nil {
			return err
		}
	}
	if shared != nil {
		t := time.Now()
		err = errors.Join(admin.Close(), shared.pool.Close(), shared.close())
		shared = nil
		report["suite_cleanup_seconds"] = time.Since(t).Seconds()
		if err != nil {
			return err
		}
	}
	report["suite_wall_seconds"] = time.Since(begin).Seconds()
	report["runner_cpu_seconds"] = cpuSelf() - self
	var children syscall.Rusage
	syscall.Getrusage(syscall.RUSAGE_CHILDREN, &children)
	childCPU := func(u syscall.Rusage) float64 {
		return float64(u.Utime.Sec+u.Stime.Sec) + float64(u.Utime.Usec+u.Stime.Usec)/1e6
	}
	report["waited_children_cpu_seconds"] = childCPU(children) - childCPU(childrenBefore)
	report["waited_children_maxrss_raw"] = children.Maxrss
	var host syscall.Rusage
	syscall.Getrusage(syscall.RUSAGE_SELF, &host)
	report["runner_maxrss_raw"] = host.Maxrss
	if backend == "mariamem" {
		if _, e := runtimePID(); e == nil {
			return errors.New("Wasmer child remains after cleanup")
		}
	}
	report["cleanup"] = map[string]any{"all_close_calls_succeeded": true, "no_observed_wasmer_child": backend == "mariamem"}
	if report["server_version"] == "" {
		return errors.New("server version missing")
	}
	report["completed"] = true
	return nil
}
func version(ctx context.Context, p *sql.DB) string {
	var v string
	_ = p.QueryRowContext(ctx, "SELECT VERSION()").Scan(&v)
	return v
}
