package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"hash/crc32"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"sync"
	"time"

	"github.com/masahitojp/mariamem"
)

type resource struct {
	RSS     int64   `json:"rss_bytes"`
	Primary int64   `json:"primary_bytes"`
	Private *int64  `json:"private_bytes"`
	CPU     float64 `json:"cpu_seconds"`
	Error   string  `json:"error,omitempty"`
}
type groupCost struct {
	Members    map[string]resource `json:"members"`
	Primary    int64               `json:"primary_bytes"`
	RSS        int64               `json:"rss_bytes"`
	Private    *int64              `json:"private_bytes"`
	Collection float64             `json:"collection_seconds"`
	At         float64             `json:"at_seconds"`
}

var collectionLock sync.Mutex

func resourceCost() (c groupCost, err error) {
	collectionLock.Lock()
	defer collectionLock.Unlock()
	begin := time.Now()
	ps, e := readCost()
	if e != nil {
		return c, e
	}
	args := []string{strconv.Itoa(os.Getpid())}
	for pid := range ps.Members {
		args = append(args, pid)
	}
	data, e := exec.Command(os.Getenv("MARIAMEM_COST_HELPER"), args...).Output()
	if e != nil {
		return c, e
	}
	if e = json.Unmarshal(data, &c.Members); e != nil {
		return c, e
	}
	if len(c.Members) != len(args) {
		return c, errors.New("process counter inventory mismatch")
	}
	for _, pid := range args {
		if _, ok := c.Members[pid]; !ok {
			return c, errors.New("missing process counters")
		}
	}
	for _, m := range c.Members {
		if m.Error == "" && (m.Primary <= 0 || m.RSS <= 0 || m.CPU < 0) {
			return c, errors.New("invalid process counters")
		}
		c.Primary += m.Primary
		c.RSS += m.RSS
		if m.Private != nil {
			if c.Private == nil {
				v := int64(0)
				c.Private = &v
			}
			*c.Private += *m.Private
		}
	}
	c.Collection = time.Since(begin).Seconds()
	return c, nil
}
func (r *runner) ariaBatch(s *mariamem.Snapshot, n int) (row map[string]any, err error) {
	baseline, err := resourceCost()
	if err != nil {
		return nil, err
	}
	if baseline.Members[strconv.Itoa(os.Getpid())].Error != "" {
		return nil, errors.New("G(0) counters unavailable")
	}
	if len(baseline.Members) != 1 {
		return nil, errors.New("G(0) has live runtime descendants")
	}
	samples := []groupCost{}
	stop := make(chan struct{})
	done := make(chan struct{})
	var monitorErr error
	begin := time.Now()
	go func() {
		defer close(done)
		for {
			c, e := resourceCost()
			if e != nil {
				monitorErr = e
				return
			}
			c.At = time.Since(begin).Seconds()
			samples = append(samples, c)
			select {
			case <-stop:
				return
			case <-time.After(time.Duration(r.cfg.interval * 1e9)):
			}
		}
	}()
	type result struct {
		db  *mariamem.Database
		row map[string]any
		err error
	}
	out := make(chan result, n)
	gate := make(chan struct{})
	for range n {
		go func() { <-gate; db, v, e := r.startup(s, begin); out <- result{db, v, e} }()
	}
	close(gate)
	dbs := []*mariamem.Database{}
	rows := []map[string]any{}
	wall := 0.0
	for range n {
		x := <-out
		err = errors.Join(err, x.err)
		if x.db != nil {
			dbs = append(dbs, x.db)
			rows = append(rows, x.row)
			wall = max(wall, x.row["ready_at_seconds"].(float64))
		}
	}
	ready, e := resourceCost()
	ready.At = time.Since(begin).Seconds()
	err = errors.Join(err, e)
	close(stop)
	<-done
	err = errors.Join(err, monitorErr)
	cpu := 0.0
	for pid, m := range ready.Members {
		if m.Error != "" {
			err = errors.Join(err, errors.New(m.Error))
		}
		cpu += m.CPU - baseline.Members[pid].CPU
	}
	// Measurement boundary ends before correctness SQL or cleanup.
	if len(ready.Members) != n+1 {
		err = errors.Join(err, errors.New("ready group process inventory mismatch"))
	}
	for _, db := range dbs {
		if err == nil {
			err = r.ariaCache(db)
		}
		err = errors.Join(err, db.Close())
	}
	after, e := resourceCost()
	after.At = time.Since(begin).Seconds()
	err = errors.Join(err, e)
	if after.Members[strconv.Itoa(os.Getpid())].Error != "" {
		err = errors.Join(err, errors.New("after-close counters unavailable"))
	}
	if len(after.Members) != 1 {
		err = errors.Join(err, errors.New("orphan runtime after Close"))
	}
	if err != nil {
		return nil, err
	}
	peak := ready.Primary
	for _, c := range samples {
		peak = max(peak, c.Primary)
	}
	return map[string]any{"per_db": rows, "workers": n, "group_ready_seconds": wall, "baseline": baseline, "ready": ready, "after_close": after, "memory_samples": samples, "group_peak_primary_bytes": peak, "incremental_peak_primary_bytes": peak - baseline.Primary, "incremental_primary_bytes": ready.Primary - baseline.Primary, "average_incremental_bytes": float64(ready.Primary-baseline.Primary) / float64(n), "combined_cpu_seconds": cpu, "host_cpu_seconds": ready.Members[strconv.Itoa(os.Getpid())].CPU - baseline.Members[strconv.Itoa(os.Getpid())].CPU, "runtime_cpu_seconds": cpu - (ready.Members[strconv.Itoa(os.Getpid())].CPU - baseline.Members[strconv.Itoa(os.Getpid())].CPU)}, nil
}
func (r *runner) ariaCorrect(db *mariamem.Database, expectedCRC uint64) (err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	p, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	defer p.Close()
	if err = r.ariaCache(db); err != nil {
		return err
	}
	p.SetMaxOpenConns(1)
	// Cache-overflow and internal temp-table coverage is separate from timed 1k Forks.
	var value, totalLength int
	var checksum uint64
	if err = p.QueryRowContext(ctx, "SELECT COUNT(*), SUM(CHAR_LENGTH(payload)), SUM(CRC32(payload)) FROM aria_probe").Scan(&value, &totalLength, &checksum); err != nil {
		return err
	}
	if value != 24000 || totalLength != 24000*2048 || checksum != expectedCRC {
		return fmt.Errorf("Aria persisted payload/count mismatch: count=%d, length=%d, CRC sum=%d", value, totalLength, checksum)
	}

	var before, after int
	var status string
	if err = p.QueryRowContext(ctx, "SHOW SESSION STATUS LIKE 'Created_tmp_disk_tables'").Scan(&status, &before); err != nil {
		return err
	}
	if _, err = p.ExecContext(ctx, "SET SESSION tmp_table_size=16384, max_heap_table_size=16384"); err != nil {
		return err
	}
	if err = p.QueryRowContext(ctx, "SELECT COUNT(*) FROM (SELECT payload,COUNT(*) AS n FROM aria_probe GROUP BY payload) AS t").Scan(&value); err != nil || value != 24000 {
		return fmt.Errorf("temporary grouping mismatch: %w", err)
	}
	if err = p.QueryRowContext(ctx, "SHOW SESSION STATUS LIKE 'Created_tmp_disk_tables'").Scan(&status, &after); err != nil {
		return err
	}
	if after <= before {
		return errors.New("disk-backed internal temporary table not exercised")
	}
	if _, err = p.ExecContext(ctx, "INSERT INTO aria_probe VALUES(99999, 'fork-local mutation')"); err != nil {
		return err
	}
	return nil
}
func (r *runner) ariaCache(db *mariamem.Database) error {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	p, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	defer p.Close()
	var bytes int
	if err = p.QueryRowContext(ctx, "SELECT @@aria_pagecache_buffer_size").Scan(&bytes); err != nil {
		return err
	}
	want, err := strconv.Atoi(os.Getenv("MARIAMEM_EXPERIMENT_ARIA_MIB"))
	if err != nil || (want != 16 && want != 128) {
		return errors.New("invalid Aria experiment condition")
	}
	if bytes != want*1024*1024 {
		return fmt.Errorf("cache configuration mismatch: got %d, expected %d", bytes, want*1024*1024)
	}
	return nil
}
func (r *runner) ariaRun() (err error) {
	if os.Getenv("MARIAMEM_COST_HELPER") == "" {
		return errors.New("native cost helper required")
	}
	os.Setenv("MARIAMEM_EXPERIMENT_ARIA_MIB", "128")
	db, initial, err := r.startup(nil, time.Now())
	if err != nil {
		return err
	}
	defer db.Close()
	r.version = initial["server_version"].(string)
	if err = r.seed(db); err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	// Normal 1k timed snapshot; a separate larger Aria correctness snapshot below.
	if err = db.WaitDisconnected(ctx); err != nil {
		return err
	}
	s, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		return err
	}
	defer s.Close()
	checkDB, _, err := r.startup(s, time.Now())
	if err != nil {
		return err
	}
	defer checkDB.Close()
	p, err := sql.Open("mysql", checkDB.DSN())
	if err != nil {
		return err
	}
	_, err = p.ExecContext(ctx, "CREATE TABLE aria_probe(id INT PRIMARY KEY,payload VARCHAR(2048)) ENGINE=Aria ROW_FORMAT=PAGE")
	if err != nil {
		p.Close()
		return err
	}
	var expectedCRC uint64
	for start := 0; start < 24000; start += 1000 {
		query := "INSERT INTO aria_probe VALUES"
		args := []any{}
		for i := start; i < start+1000; i++ {
			if i > start {
				query += ","
			}
			query += "(?,?)"
			payload := fmt.Sprintf("%08d", i) + string(makePayload(2040))
			expectedCRC += uint64(crc32.ChecksumIEEE([]byte(payload)))
			args = append(args, i, payload)
		}
		if _, err = p.ExecContext(ctx, query, args...); err != nil {
			p.Close()
			return err
		}
	}
	p.Close()
	if err = checkDB.WaitDisconnected(ctx); err != nil {
		return err
	}
	large, err := checkDB.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		return err
	}
	defer large.Close()
	var dataBytes int64
	if err = filepath.Walk(large.Path(), func(path string, info os.FileInfo, e error) error {
		if e != nil {
			return e
		}
		if info.Name() == "aria_probe.MAD" {
			dataBytes += info.Size()
		}
		return nil
	}); err != nil {
		return err
	}
	if dataBytes <= 16*1024*1024 {
		return fmt.Errorf("Aria fixture does not exceed 16MiB cache: %d", dataBytes)
	}
	r.samples = append(r.samples, map[string]any{"case": "aria_correctness", "phase": "correctness", "data_file_bytes": dataBytes, "rows": 24000, "payload_bytes": 2048, "payload_crc32_sum": expectedCRC})
	// Auxiliary over-cache workload, five balanced fresh forks per condition.
	for round := 0; round < 5; round++ {
		order := []string{"128", "16"}
		if round%2 != 0 {
			order[0], order[1] = order[1], order[0]
		}
		for _, mode := range order {
			os.Setenv("MARIAMEM_EXPERIMENT_ARIA_MIB", mode)
			d, _, e := r.startup(large, time.Now())
			if e != nil {
				return e
			}
			before, e := resourceCost()
			if e != nil {
				d.Close()
				return e
			}
			begin := time.Now()
			e = r.ariaCorrect(d, expectedCRC)
			elapsed := time.Since(begin).Seconds()
			after, ce := resourceCost()
			cleanup := d.Close()
			if e = errors.Join(e, ce, cleanup); e != nil {
				return e
			}
			cpu := 0.0
			for pid, m := range after.Members {
				if m.Error != "" {
					return errors.New(m.Error)
				}
				cpu += m.CPU - before.Members[pid].CPU
			}
			r.samples = append(r.samples, map[string]any{"case": "aria_over_cache", "phase": "measurement", "condition": mode, "round": round, "wall_seconds": elapsed, "combined_cpu_seconds": cpu, "before": before, "after": after, "correctness": "cache-size, full payload scan, disk-backed internal temp table, fork-local mutation: PASS"})
		}
	}

	// Timed rows use only the canonical 1k fixture; ariaCorrect is not run there.
	for _, n := range []int{1, 4, 8} {
		for i := 0; i < r.cfg.runs+r.cfg.warmup; i++ {
			order := []string{"128", "16"}
			if i%2 != 0 {
				order[0], order[1] = order[1], order[0]
			}
			for _, mode := range order {
				os.Setenv("MARIAMEM_EXPERIMENT_ARIA_MIB", mode)
				row, e := r.ariaBatch(s, n)
				if e != nil {
					return e
				}
				row["case"] = "fork"
				row["condition"] = mode
				row["round"] = i
				row["phase"] = "measurement"
				if i < r.cfg.warmup {
					row["phase"] = "warmup"
				}
				row["memory_metric"] = "linux_pss"
				if runtime.GOOS == "darwin" {
					row["memory_metric"] = "macos_phys_footprint_sum"
				}
				r.samples = append(r.samples, row)
			}
		}
	}
	return nil
}
func makePayload(n int) []byte {
	b := make([]byte, n)
	for i := range b {
		b[i] = 'x'
	}
	return b
}
