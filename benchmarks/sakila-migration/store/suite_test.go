package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/sakila-migration/internal/trace"
)

var backend = flag.String("sakila.backend", "mariamem", "mariamem or mysql (the driver starts external servers)")
var metricsPath = flag.String("sakila.metrics", "", "path for a JSON timing report")
var sourceCommit string

type suite struct {
	snap   *mariamem.Snapshot
	report trace.Report
	mu     sync.Mutex
}

func ms(d time.Duration) float64 {
	return float64(d) / float64(time.Millisecond)
}

func (s *suite) record(phaseName, name string, f func() error) error {
	start := trace.MonotonicNS()
	err := f()
	end := trace.MonotonicNS()
	s.mu.Lock()
	s.report.Phases = append(s.report.Phases, trace.Phase{Name: phaseName, Case: name, From: ms(time.Duration(start - s.report.StartMonoNS)), To: ms(time.Duration(end - s.report.StartMonoNS))})
	s.mu.Unlock()
	return err
}

func TestSakila(t *testing.T) {
	ctx, cancel := context.WithTimeout(t.Context(), 3*time.Minute)
	defer cancel()
	s := suite{report: trace.Report{Backend: *backend, SourceCommit: sourceCommit}}
	s.report.StartNS = time.Now().UnixNano()
	s.report.StartMonoNS = trace.MonotonicNS()
	if _, err := fmt.Sscan(flag.Lookup("test.parallel").Value.String(), &s.report.Parallel); err != nil {
		t.Fatal(err)
	}
	var admin *sql.DB
	var stop func() error
	var err error
	dsn := os.Getenv("SAKILA_MYSQL_DSN")
	switch *backend {
	case "mariamem":
		stop, err = s.embedded(ctx)
	case "mysql":
		admin, err = openDB(dsn)
		if err == nil {
			stop = admin.Close
			err = s.record("ready", "", func() (err error) {
				s.report.Version, err = waitReady(ctx, admin)
				return err
			})
		}
		if err == nil {
			s.report.Settings, err = config(admin, ctx)
		}
	default:
		t.Fatalf("unexpected benchmark backend %q", *backend)
	}
	if stop != nil {
		defer func() {
			if err := s.record("cleanup", "", stop); err != nil {
				t.Error(err)
			}
			if t.Failed() || *metricsPath == "" {
				return
			}
			s.report.TotalMS = ms(time.Duration(trace.MonotonicNS() - s.report.StartMonoNS))
			data, err := json.Marshal(s.report)
			if err == nil {
				err = os.WriteFile(*metricsPath, append(data, '\n'), 0644)
			}
			if err != nil {
				t.Error(err)
			}
		}()
	}
	if err != nil {
		t.Fatal(err)
	}
	if s.snap == nil {
		if err := s.record("fixture", "", func() error {
			return fixture(ctx, admin)
		}); err != nil {
			t.Fatal(err)
		}
		for variant := 1; variant <= 8; variant++ {
			name := fmt.Sprintf("late_fee/%02d", variant)
			if !t.Run(name, func(t *testing.T) {
				s.runSharedMigration(t, ctx, name, variant, admin)
			}) {
				break
			}
		}
	} else {
		t.Run("migration", func(t *testing.T) {
			for variant := 1; variant <= 8; variant++ {
				name := fmt.Sprintf("late_fee/%02d", variant)
				t.Run(name, func(t *testing.T) {
					t.Parallel()
					s.runMigration(t, ctx, name, variant)
				})
			}
		})
	}

	if s.report.Writes != 8 {
		t.Errorf("completed %d cases, want 8", s.report.Writes)
	}
}

func (s *suite) runMigration(t *testing.T, ctx context.Context, name string, variant int) {
	var db *sql.DB
	var dispose func() error
	defer func() {
		if err := s.record("case_cleanup", name, func() error {
			var err error
			if db != nil {
				err = db.Close()
			}
			if dispose != nil {
				err = errors.Join(err, dispose())
			}
			return err
		}); err != nil {
			t.Error(err)
		}
	}()
	if err := s.record("case_setup", name, func() (err error) {
		child, err := s.snap.Fork(ctx)
		if err != nil {
			return err
		}
		dispose = child.Close
		db, err = openDB(child.DSN())
		return err
	}); err != nil {
		t.Fatal(err)
	}
	if err := s.record("variant", name, func() error { return prepareMigration(ctx, db, variant) }); err != nil {
		t.Fatal(err)
	}
	if err := s.record("write", name, func() error { return migrateAndVerify(ctx, db, variant) }); err != nil {
		t.Fatal(err)
	}
	s.mu.Lock()
	s.report.Writes++
	s.mu.Unlock()
}

func (s *suite) embedded(ctx context.Context) (stop func() error, err error) {
	var parent *mariamem.Database
	stop = func() error {
		var cleanup error
		if s.snap != nil {
			cleanup = errors.Join(cleanup, s.snap.Close())
		}
		if parent != nil {
			cleanup = errors.Join(cleanup, parent.Close())
		}
		return cleanup
	}
	var pool *sql.DB
	if err := s.record("ready", "", func() (err error) {
		parent, err = mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			return err
		}
		pool, err = openDB(parent.DSN())
		if err != nil {
			return err
		}
		s.report.Version, err = waitReady(ctx, pool)
		return err
	}); err != nil {
		if pool != nil {
			pool.Close()
		}
		return stop, err
	}
	defer pool.Close()
	s.report.Settings, err = config(pool, ctx)
	if err != nil {
		return stop, err
	}
	if err := s.record("fixture", "", func() error { return fixture(ctx, pool) }); err != nil {
		return stop, err
	}
	if err := s.record("snapshot", "", func() error {
		if err := pool.Close(); err != nil {
			return err
		}
		if err := parent.WaitDisconnected(ctx); err != nil {
			return err
		}
		var err error
		s.snap, err = parent.Snapshot(ctx, mariamem.SnapshotOptions{})
		return err
	}); err != nil {
		return stop, err
	}
	return stop, nil
}

func (s *suite) runSharedMigration(t *testing.T, ctx context.Context, name string, variant int, db *sql.DB) {
	if variant > 1 {
		if err := s.record("reset", name, func() error { return resetMigration(ctx, db) }); err != nil {
			t.Fatal(err)
		}
	}
	if err := s.record("variant", name, func() error { return prepareMigration(ctx, db, variant) }); err != nil {
		t.Fatal(err)
	}
	if err := s.record("write", name, func() error { return migrateAndVerify(ctx, db, variant) }); err != nil {
		t.Fatal(err)
	}
	s.report.Writes++
}

func resetMigration(ctx context.Context, db *sql.DB) error {
	conn, err := db.Conn(ctx)
	if err != nil {
		return err
	}
	defer conn.Close()
	for _, statement := range []string{
		"DROP TRIGGER rental_late_fee",
		"DROP TABLE late_fee",
		// The new composite index can replace InnoDB's implicit FK index.
		// Recreate payment from its pre-migration DDL to restore both.
		"DROP TABLE payment",
		"TRUNCATE TABLE rental_audit",
		"TRUNCATE TABLE rental",
		paymentDDL,
	} {
		if _, err := conn.ExecContext(ctx, statement); err != nil {
			return fmt.Errorf("%s: %w", statement, err)
		}
	}
	for _, statement := range transactionSeed {
		if _, err := conn.ExecContext(ctx, statement); err != nil {
			return fmt.Errorf("restore transaction seed: %w", err)
		}
	}
	return nil
}
