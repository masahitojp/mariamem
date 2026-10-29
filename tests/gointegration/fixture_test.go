//go:build integration

package gointegration_test

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"sync/atomic"
	"testing"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem/mariamemtest"
)

func fixtureOptions(calls *atomic.Int32) mariamemtest.Options {
	return mariamemtest.Options{MaxForks: 2, Prepare: func(ctx context.Context, pool *sql.DB, _ string) error {
		calls.Add(1)
		for _, q := range []string{"CREATE TABLE fixture_items (id INT PRIMARY KEY, label VARCHAR(32)) ENGINE=InnoDB", "INSERT INTO fixture_items VALUES (1, 'seed')"} {
			if _, err := pool.ExecContext(ctx, q); err != nil {
				return err
			}
		}
		return nil
	}}
}
func fixtureSeed(t *testing.T, p *sql.DB) {
	t.Helper()
	var n int
	var label string
	if err := p.QueryRowContext(t.Context(), "SELECT COUNT(*), MIN(label) FROM fixture_items").Scan(&n, &label); err != nil || n != 1 || label != "seed" {
		t.Fatalf("starting data %d/%q: %v", n, label, err)
	}
	// Parameterized SQL exercises the helper's normal prepared-driver path.
	if err := p.QueryRowContext(t.Context(), "SELECT label FROM fixture_items WHERE id=?", 1).Scan(&label); err != nil || label != "seed" {
		t.Fatalf("prepared parameter/result %q: %v", label, err)
	}
	if err := p.QueryRowContext(t.Context(), "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='fixture_items'").Scan(&n); err != nil || n != 2 {
		t.Fatalf("starting schema %d: %v", n, err)
	}
}

func TestFixturePreparedChildren(t *testing.T) {
	var calls atomic.Int32
	f, err := mariamemtest.New(t.Context(), fixtureOptions(&calls))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := f.Close(); err != nil {
			t.Error(err)
		}
	})
	for _, order := range [][]int{{0, 1}, {1, 0}} {
		for _, kind := range order {
			t.Run(fmt.Sprintf("sequential%d", kind), func(t *testing.T) {
				p := f.DB(t)
				fixtureSeed(t, p)
				if p != f.DB(t) {
					t.Fatal("repeated DB(t) allocated another child")
				}
				if _, err := p.ExecContext(t.Context(), "UPDATE fixture_items SET label='changed'"); err != nil {
					t.Fatal(err)
				}
				if kind == 0 {
					if _, err := p.ExecContext(t.Context(), "ALTER TABLE fixture_items ADD extra INT"); err != nil {
						t.Fatal(err)
					}
				}
			})
		}
	}
	t.Run("parallel", func(t *testing.T) {
		for i := 0; i < 4; i++ {
			t.Run(fmt.Sprint(i), func(t *testing.T) {
				t.Parallel()
				p := f.DB(t)
				fixtureSeed(t, p)
				if _, err := p.ExecContext(t.Context(), "DELETE FROM fixture_items"); err != nil {
					t.Fatal(err)
				}
			})
		}
	})
	if calls.Load() != 1 {
		t.Fatal("preparation repeated", calls.Load())
	}
}

// A real failing subtest must clean up its committed mutation. Keep that failure
// in a subprocess so this oracle itself does not turn CI red.
func TestFixtureOrdinaryFailure(t *testing.T) {
	if os.Getenv("MARIAMEM_FIXTURE_FAIL_CHILD") == "1" {
		var calls atomic.Int32
		f, err := mariamemtest.New(t.Context(), fixtureOptions(&calls))
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() {
			if err := f.Close(); err != nil {
				t.Error(err)
			}
		})
		t.Run("intentional_failure", func(t *testing.T) {
			p := f.DB(t)
			fixtureSeed(t, p)
			if _, err := p.ExecContext(t.Context(), "DELETE FROM fixture_items"); err != nil {
				t.Fatal(err)
			}
			t.Fatal("intentional fixture failure")
		})
		t.Run("healthy_after_failure", func(t *testing.T) { fixtureSeed(t, f.DB(t)); t.Log("PREPARED_SEED_PRESERVED") })
		return
	}
	binary, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	cmd := exec.CommandContext(t.Context(), binary, "-test.run=^TestFixtureOrdinaryFailure$", "-test.v")
	cmd.Env = append(os.Environ(), "MARIAMEM_FIXTURE_FAIL_CHILD=1")
	out, err := cmd.CombinedOutput()
	var exit *exec.ExitError
	if !errors.As(err, &exit) || exit.ExitCode() != 1 || !strings.Contains(string(out), "intentional fixture failure") || !strings.Contains(string(out), "PREPARED_SEED_PRESERVED") || !strings.Contains(string(out), "--- PASS: TestFixtureOrdinaryFailure/healthy_after_failure") {
		t.Fatalf("failure/isolation oracle: %v\n%s", err, out)
	}
}

func TestFixturePrepareSQLError(t *testing.T) {
	f, err := mariamemtest.New(t.Context(), mariamemtest.Options{Prepare: func(ctx context.Context, p *sql.DB, _ string) error {
		_, err := p.ExecContext(ctx, "SELECT * FROM fixture_missing_table")
		return err
	}})
	var sqlErr *mysql.MySQLError
	var detail *mariamemtest.Error
	if f != nil || !errors.As(err, &sqlErr) || sqlErr.Number != 1146 || string(sqlErr.SQLState[:]) != "42S02" || !errors.As(err, &detail) || detail.Stage != "prepare" || detail.CleanupState != "completed" {
		t.Fatalf("original SQL failure/cleanup: fixture=%v error=%v", f, err)
	}
}
