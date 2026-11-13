package store_test

// The same ten tests run on two execution models.
//
// pgmem (the default): TestMain boots a server in this process, imports
// the schema and master data once and takes a snapshot. Read-only tests
// use that server itself, loaded with the sample data once after the
// snapshot; only a test that writes forks its own copy. Everything after
// the snapshot runs in parallel.
//
// Conventional (MODELCASE_DSN set): one PostgreSQL server that a driver
// started before the test binary. The schema and master data go into the
// shared database once. Read-only tests still run in parallel on it, but
// a test that writes has to run alone: it resets the shared data, loads
// the sample data and runs, and the next writer waits.
//
// MODELCASE_TRACE=path writes the timing of every node as JSON; the
// benchmark driver sets it, plain go test does not need it.

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"sync"
	"testing"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/stdlib"

	"github.com/shibukawa/pgmem"
	"github.com/shibukawa/pgmem/bench/modelcase/internal/trace"
	"github.com/shibukawa/pgmem/bench/modelcase/store"
)

var fx *fixture

type fixture struct {
	rec            *trace.Recorder
	parallelWrites bool
	// isolated gives a writing test a database in the sample state that
	// nobody else uses (pgmem: a fresh fork) or, on the shared server,
	// the shared database reset to that state.
	isolated func(t *testing.T) *sql.DB
	// shared is the database read-only tests share, prepared on first use.
	shared    func() *sql.DB
	sharedDB  *sql.DB
	sharedErr error
	once      sync.Once
	close     func()
}

func TestMain(m *testing.M) {
	fx = &fixture{rec: trace.New()}
	ctx := context.Background()
	var err error
	if dsn := os.Getenv("MODELCASE_DSN"); dsn != "" {
		err = fx.useServer(ctx, dsn)
	} else {
		err = fx.usePgmem(ctx)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	code := m.Run()
	if fx.sharedDB != nil {
		fx.sharedDB.Close()
	}
	fx.close()
	if err := fx.rec.Write(os.Getenv("MODELCASE_TRACE")); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	os.Exit(code)
}

// usePgmem: boot, import, snapshot; then the template for readers and a
// fork per writer.
func (f *fixture) usePgmem(ctx context.Context) error {
	f.parallelWrites = true
	done := f.rec.Start("boot", "boot", "setup")
	srv, err := pgmem.Start(ctx, pgmem.Options{Database: "app"})
	if err != nil {
		return err
	}
	done()
	f.rec.Set("model", "pgmem")

	done = f.rec.Start("import", "import", "setup")
	db := openInProcess(srv)
	if err := prepare(ctx, db); err != nil {
		return err
	}
	f.rec.Set("server_version", version(ctx, db))
	db.Close()
	done()

	done = f.rec.Start("snapshot", "snapshot", "setup")
	snap, err := srv.Snapshot(ctx, pgmem.SnapshotOptions{})
	if err != nil {
		return err
	}
	done()

	f.isolated = func(t *testing.T) *sql.DB {
		t.Helper()
		done := f.rec.Start("fork", "fork", t.Name())
		s, err := snap.Fork(ctx)
		if err != nil {
			t.Fatal(err)
		}
		done()
		db := openInProcess(s)
		t.Cleanup(func() { db.Close(); s.Close() })
		done = f.rec.Start("sample", "sample", t.Name())
		if err := store.LoadSample(ctx, db); err != nil {
			t.Fatal(err)
		}
		done()
		return db
	}
	// Readers need no copy: the snapshot is taken, so the sample data can
	// go into the template server and the forks stay clean.
	f.shared = func() *sql.DB {
		f.once.Do(func() {
			db := openInProcess(srv)
			done := f.rec.Start("sample", "sample", "shared")
			if f.sharedErr = store.LoadSample(ctx, db); f.sharedErr == nil {
				f.sharedDB = db
			}
			done()
		})
		return f.sharedDB
	}
	f.close = func() {
		snap.Close()
		srv.Close()
	}
	return nil
}

// useServer: one shared database on a server somebody else started.
func (f *fixture) useServer(ctx context.Context, dsn string) error {
	f.parallelWrites = false
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		return err
	}
	done := f.rec.Start("import", "import", "setup")
	if err := prepare(ctx, db); err != nil {
		return err
	}
	f.rec.Set("model", "server")
	f.rec.Set("server_version", version(ctx, db))
	done()

	reload := func(lane string) error {
		done := f.rec.Start("reset", "reset", lane)
		if err := store.ResetSample(ctx, db); err != nil {
			return err
		}
		done()
		done = f.rec.Start("sample", "sample", lane)
		if err := store.LoadSample(ctx, db); err != nil {
			return err
		}
		done()
		return nil
	}
	f.isolated = func(t *testing.T) *sql.DB {
		t.Helper()
		if err := reload(t.Name()); err != nil {
			t.Fatal(err)
		}
		return db
	}
	f.shared = func() *sql.DB {
		f.once.Do(func() {
			f.sharedErr = reload("shared")
			if f.sharedErr == nil {
				f.sharedDB = db
			}
		})
		return f.sharedDB
	}
	f.close = func() { db.Close() }
	return nil
}

// prepare is the work every model does once: migrations and master data.
func prepare(ctx context.Context, db *sql.DB) error {
	if err := store.Migrate(ctx, db); err != nil {
		return fmt.Errorf("migrate: %w", err)
	}
	if err := store.SeedMaster(ctx, db); err != nil {
		return fmt.Errorf("seed: %w", err)
	}
	return nil
}

func version(ctx context.Context, db *sql.DB) string {
	var v string
	db.QueryRowContext(ctx, "SHOW server_version").Scan(&v)
	return v
}

func openInProcess(s *pgmem.Server) *sql.DB {
	cfg, err := pgx.ParseConfig(s.DSN())
	if err != nil {
		panic(err)
	}
	cfg.DialFunc = s.Dial
	return stdlib.OpenDB(*cfg)
}

// Group is the entry point of a scenario, a top-level test whose cases are
// subtests. Read-only scenarios run in parallel with each other on both
// models; writing scenarios only where their cases may.
func (f *fixture) Group(t *testing.T, writes bool) {
	t.Helper()
	if !writes || f.parallelWrites {
		t.Parallel()
	}
}

// Read is the entry point of a read-only test: it runs in parallel on the
// shared copy. The test body is recorded as one span.
func (f *fixture) Read(t *testing.T) *sql.DB {
	t.Helper()
	t.Parallel()
	db := f.shared()
	if f.sharedErr != nil {
		t.Fatal(f.sharedErr)
	}
	t.Cleanup(f.rec.Start("test", "read", t.Name()))
	return db
}

// Write is the entry point of a test that modifies data: its own copy on
// pgmem, the reset shared database otherwise. Only pgmem lets it run in
// parallel with the other tests.
func (f *fixture) Write(t *testing.T) *sql.DB {
	t.Helper()
	if f.parallelWrites {
		t.Parallel()
	}
	db := f.isolated(t)
	t.Cleanup(f.rec.Start("test", "write", t.Name()))
	return db
}
