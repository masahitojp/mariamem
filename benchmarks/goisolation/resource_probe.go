package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"strconv"
	"sync"
	"time"

	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func groupCPU(before, after groupCost) (host, runtime float64) {
	parent := strconv.Itoa(os.Getpid())
	for pid, m := range after.Members {
		delta := m.CPU - before.Members[pid].CPU
		if pid == parent {
			host += delta
		} else {
			runtime += delta
		}
	}
	return
}

// Samples use the same counters as baseline/ready; CPU ends at ready collection,
// before post-ready correctness checks and cleanup. Sampling overhead is included.
func (r *runner) resourceBatch(saved *mariamem.Snapshot, n int) (row map[string]any, err error) {
	baseline, err := resourceCost()
	if err != nil {
		return nil, err
	}
	if len(baseline.Members) != 1 {
		return nil, errors.New("G(0) has live runtime descendants")
	}
	row = map[string]any{"workers": n, "baseline": baseline}
	samples := []groupCost{}
	gaps := []map[string]any{}
	stop, done := make(chan struct{}), make(chan struct{})
	begin := time.Now()
	go func() {
		defer close(done)
		for {
			c, e := resourceCost()
			c.At = time.Since(begin).Seconds()
			if e != nil {
				gaps = append(gaps, map[string]any{"at_seconds": c.At, "error": e.Error()})
			} else {
				samples = append(samples, c)
			}
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
	results := make(chan result, n)
	gate := make(chan struct{})
	for range n {
		go func() { <-gate; db, v, e := r.startup(saved, begin); results <- result{db, v, e} }()
	}
	close(gate)
	dbs := []*mariamem.Database{}
	rows := []map[string]any{}
	wall := 0.0
	for range n {
		x := <-results
		err = errors.Join(err, x.err)
		if x.db != nil {
			dbs = append(dbs, x.db)
		}
		if x.row != nil {
			rows = append(rows, x.row)
			wall = max(wall, x.row["ready_at_seconds"].(float64))
		}
	}
	ready, e := resourceCost()
	ready.At = time.Since(begin).Seconds()
	err = errors.Join(err, e)
	close(stop)
	<-done
	row["per_db"], row["group_ready_seconds"], row["latency_seconds"] = rows, wall, wall
	row["ready"], row["memory_samples"], row["memory_sampling_gaps"] = ready, samples, gaps
	if e == nil {
		host, runtime := groupCPU(baseline, ready)
		row["host_cpu_seconds"], row["runtime_cpu_seconds"], row["combined_cpu_seconds"] = host, runtime, host+runtime
		row["incremental_primary_bytes"] = ready.Primary - baseline.Primary
		row["average_incremental_bytes"] = float64(ready.Primary-baseline.Primary) / float64(n)
		if len(ready.Members) != n+1 {
			err = errors.Join(err, errors.New("ready process inventory mismatch"))
		}
	}
	peak := ready.Primary
	for _, s := range samples {
		peak = max(peak, s.Primary)
	}
	row["group_peak_primary_bytes"], row["incremental_peak_primary_bytes"] = peak, peak-baseline.Primary
	if r.cfg.resourceProbe == "attribution" && len(rows) == 1 {
		row["ready_mapping_observation"] = processDiagnostics(rows[0])
	}
	closeBegin := time.Now()
	for _, db := range dbs {
		err = errors.Join(err, db.Close())
	}
	after, e := resourceCost()
	err = errors.Join(err, e)
	row["after_close"], row["cleanup_seconds"] = after, time.Since(closeBegin).Seconds()
	if e == nil && len(after.Members) != 1 {
		err = errors.Join(err, errors.New("orphan runtime after Close"))
	}
	row["completed"] = err == nil
	return row, err
}

func (r *runner) sessionProbe() (row map[string]any, err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, stage, err := r.startup(nil, time.Now())
	if err != nil {
		return nil, err
	}
	row = map[string]any{"startup": stage, "sessions": 16}
	defer func() {
		err = errors.Join(err, db.Close())
		after, e := resourceCost()
		row["after_database_close"] = after
		err = errors.Join(err, e)
		if e == nil && len(after.Members) != 1 {
			err = errors.Join(err, errors.New("orphan session runtime"))
		}
		row["completed"] = err == nil
	}()
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return row, err
	}
	pool.SetMaxOpenConns(17)
	pool.SetMaxIdleConns(0)
	connections := []*sql.Conn{}
	defer func() {
		for _, c := range connections {
			err = errors.Join(err, c.Close())
		}
		err = errors.Join(err, pool.Close())
	}()
	baseline, e := resourceCost()
	if e != nil {
		return row, e
	}
	row["zero_sessions"] = baseline
	durations := []float64{}
	var one groupCost
	for i := 0; i < 16; i++ {
		begin := time.Now()
		c, e := pool.Conn(ctx)
		if e != nil {
			return row, e
		}
		connections = append(connections, c)
		if e = c.PingContext(ctx); e != nil {
			return row, e
		}
		durations = append(durations, time.Since(begin).Seconds())
		if i == 0 {
			one, e = resourceCost()
			if e != nil {
				return row, e
			}
			row["one_session"] = one
		}
	}
	sixteen, e := resourceCost()
	if e != nil {
		return row, e
	}
	row["sixteen_sessions"] = sixteen
	row["connection_seconds"] = durations
	host, runtime := groupCPU(one, sixteen)
	row["one_to_sixteen_cpu_seconds"] = host + runtime
	row["one_to_sixteen_host_cpu_seconds"], row["one_to_sixteen_runtime_cpu_seconds"] = host, runtime
	row["one_to_sixteen_primary_bytes"] = sixteen.Primary - one.Primary
	var wg sync.WaitGroup
	errs := make(chan error, 16)
	for i, c := range connections {
		wg.Add(1)
		go func(i int, c *sql.Conn) {
			defer wg.Done()
			v := i + 1
			if _, e := c.ExecContext(ctx, "SET @mariamem_session_probe=?", v); e != nil {
				errs <- e
				return
			}
			if _, e := c.ExecContext(ctx, "CREATE TEMPORARY TABLE session_probe(value INT)"); e != nil {
				errs <- e
				return
			}
			if _, e := c.ExecContext(ctx, "INSERT INTO session_probe VALUES(?)", v); e != nil {
				errs <- e
				return
			}
			var ordinary, variable, temp int
			e := c.QueryRowContext(ctx, "SELECT 1,@mariamem_session_probe,(SELECT value FROM session_probe)").Scan(&ordinary, &variable, &temp)
			if e == nil && (ordinary != 1 || variable != v || temp != v) {
				e = errors.New("session variable/temporary table isolation failed")
			}
			errs <- e
		}(i, c)
	}
	wg.Wait()
	close(errs)
	for e := range errs {
		err = errors.Join(err, e)
	}
	if err != nil {
		return row, err
	}
	extra, e := pool.Conn(ctx)
	if e == nil {
		e = extra.PingContext(ctx)
		extra.Close()
	}
	var capacity *mysql.MySQLError
	if !errors.As(e, &capacity) || capacity.Number != 1040 {
		return row, fmt.Errorf("expected recoverable MySQL 1040 for session 17; got %v", e)
	}
	row["seventeenth_session_mysql_error"] = capacity.Number
	for _, c := range connections {
		if e := c.PingContext(ctx); e != nil {
			return row, e
		}
		if e := c.Close(); e != nil {
			return row, e
		}
	}
	connections = nil
	if e := pool.Close(); e != nil {
		return row, e
	}
	// Close the driver's physical sessions and await guest session-close acknowledgement.
	if e := db.WaitDisconnected(ctx); e != nil {
		return row, e
	}
	idle, e := resourceCost()
	if e != nil {
		return row, e
	}
	row["after_sessions_close"] = idle
	check, e := sql.Open("mysql", db.DSN())
	if e != nil {
		return row, e
	}
	defer check.Close()
	fresh, e := check.Conn(ctx)
	if e != nil {
		return row, e
	}
	defer fresh.Close()
	var variable sql.NullInt64
	if e = fresh.QueryRowContext(ctx, "SELECT @mariamem_session_probe").Scan(&variable); e != nil || variable.Valid {
		return row, fmt.Errorf("reused slot inherited session variable: %v", e)
	}
	var value int
	e = fresh.QueryRowContext(ctx, "SELECT value FROM session_probe").Scan(&value)
	var missing *mysql.MySQLError
	if !errors.As(e, &missing) || missing.Number != 1146 {
		return row, fmt.Errorf("reused slot retained temporary table or wrong SQL error: %v", e)
	}
	if db.Err() != nil {
		return row, db.Err()
	}
	row["isolation_passed"] = true
	row["capacity_recoverable"] = true
	return row, nil
}

func (r *runner) resourceRun() error {
	if os.Getenv("MARIAMEM_COST_HELPER") == "" {
		return errors.New("resource probe requires bounded OS counter helper")
	}
	if r.cfg.resourceProbe == "sessions" {
		row, e := r.sessionProbe()
		if row != nil {
			row["case"] = "sessions_16"
			r.samples = append(r.samples, row)
		}
		return e
	}
	if r.cfg.resourceProbe != "batch" && r.cfg.resourceProbe != "attribution" && r.cfg.resourceProbe != "fresh" {
		return errors.New("unknown resource probe")
	}
	n, e := strconv.Atoi(r.cfg.workers)
	if e != nil || n < 1 {
		return errors.New("resource probe requires one concurrency level")
	}
	if r.cfg.resourceProbe == "fresh" {
		row, err := r.resourceBatch(nil, n)
		if row != nil {
			row["case"] = "fresh_resources"
			r.samples = append(r.samples, row)
		}
		return err
	}
	db, _, e := r.startup(nil, time.Now())
	if e != nil {
		return e
	}
	defer db.Close()
	if e = r.seed(db); e != nil {
		return e
	}
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	saved, e := resourceSnapshot(ctx, db)
	if e != nil {
		return e
	}
	defer saved.Close()
	row, e := r.resourceBatch(saved, n)
	if row != nil {
		row["case"] = "fork_first_sql"
		r.samples = append(r.samples, row)
	}
	return e
}

// Driver Close only starts server-side cleanup. Snapshot must wait for its acknowledgement,
// just as the canonical isolation runner does; all of this is outside G(0)/Fork timing.
type resourceSnapshotSource interface {
	WaitDisconnected(context.Context) error
	Snapshot(context.Context, mariamem.SnapshotOptions) (*mariamem.Snapshot, error)
}

func resourceSnapshot(ctx context.Context, db resourceSnapshotSource) (*mariamem.Snapshot, error) {
	if err := db.WaitDisconnected(ctx); err != nil {
		return nil, fmt.Errorf("fixture session cleanup before Snapshot: %w", err)
	}
	saved, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		return nil, fmt.Errorf("prepared fixture Snapshot: %w", err)
	}
	return saved, nil
}
