// Package mariamemtest prepares a MariaDB baseline once and owns an independent
// database/sql pool and database for each Go test. It is intended for TestMain
// and testing.T cleanup; it does not share baselines between test processes.
package mariamemtest

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"io"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

// Options configures a fixture. Prepare may run migration commands using the
// supplied DSN. It must return their original errors and retire any connections
// it opens itself before returning. A nil callback declares an empty baseline.
type Options struct {
	DatabaseOptions  mariamem.Options
	Prepare          func(context.Context, *sql.DB, string) error
	MaxForks         int           // Zero means 2; negative values are rejected.
	OperationTimeout time.Duration // Zero means 120s; cancellation is cooperative.
}

// Error preserves both the operation failure and any cleanup failure. SQL and
// test assertion failures outside helper-owned operations keep normal Go output.
type Error struct {
	Stage        string
	Err          error
	CleanupErr   error
	CleanupState string
	Action       string
}

func (e *Error) Error() string {
	return fmt.Sprintf("mariamemtest %s: %v; dependent test admission stopped; cleanup=%s; next: %s", e.Stage, errors.Join(e.Err, e.CleanupErr), e.CleanupState, e.Action)
}
func (e *Error) Unwrap() []error {
	var causes []error
	for _, err := range []error{e.Err, e.CleanupErr} {
		if err != nil {
			causes = append(causes, err)
		}
	}
	return causes
}

func failure(stage string, cause, cleanup error) error {
	state := "completed"
	if cleanup != nil {
		state = "unconfirmed (see cleanup error)"
	} else if stage == "capture" && cause != nil {
		state = "helper owners finalized; capture-internal cleanup unverified"
	}
	action := "inspect the original error; the underlying cause may be unknown"
	switch stage {
	case "prepare":
		action = "check the preparation callback or migration command against the supplied target"
	case "disconnect":
		action = "finish transactions and retire all preparation connections before capture"
	case "capture":
		action = "inspect the original capture and cleanup errors; the underlying cause may be unknown"
		if errors.Is(cause, mariamem.ErrBusy) || errors.Is(cause, mariamem.ErrTransactionActive) {
			action = "finish transactions and retire all preparation connections before capture"
		}
	case "acquire":
		action = "release test-owned children or increase MaxForks; check cancellation and parent/subtest ownership"
	}
	return &Error{Stage: stage, Err: cause, CleanupErr: cleanup, CleanupState: state, Action: action}
}

type database interface {
	DSN() string
	WaitDisconnected(context.Context) error
	capture(context.Context) (baseline, error)
	Close() error
}
type baseline interface {
	fork(context.Context) (database, error)
	Close() error
}
type realDatabase struct{ *mariamem.Database }

func (d realDatabase) capture(ctx context.Context) (baseline, error) {
	s, err := d.Snapshot(ctx, mariamem.SnapshotOptions{Rollback: false})
	if s == nil {
		return nil, err
	}
	return realBaseline{s}, err
}

type realBaseline struct{ *mariamem.Snapshot }

func (s realBaseline) fork(ctx context.Context) (database, error) {
	d, err := s.Fork(ctx)
	if d == nil {
		return nil, err
	}
	return realDatabase{d}, err
}

type dependencies struct {
	start func(context.Context, mariamem.Options) (database, error)
	open  func(string, int, int) (*sql.DB, error)
}

func production() dependencies {
	return dependencies{
		start: func(ctx context.Context, opts mariamem.Options) (database, error) {
			d, err := mariamem.Start(ctx, opts)
			if d == nil {
				return nil, err
			}
			return realDatabase{d}, err
		},
		open: func(dsn string, maxOpen, maxIdle int) (*sql.DB, error) {
			config, err := mysql.ParseDSN(dsn)
			if err != nil {
				return nil, err
			}
			config.InterpolateParams = false
			connector, err := mysql.NewConnector(config)
			if err != nil {
				return nil, err
			}
			pool := sql.OpenDB(connector)
			pool.SetMaxOpenConns(maxOpen)
			pool.SetMaxIdleConns(maxIdle)
			return pool, nil
		},
	}
}

// Fixture owns a prepared baseline and every pool/child it supplies. Do not copy.
// Close ends all supplied handles, including those whose t.Cleanup has not run.
type Fixture struct {
	mu        sync.Mutex
	opts      Options
	deps      dependencies
	base      baseline
	entries   map[any]*child
	permits   chan struct{}
	stopped   chan struct{}
	closed    bool
	debt      error
	starting  sync.WaitGroup
	closeOnce sync.Once
	closeErr  error
}
type child struct {
	ready      chan struct{}
	pool       *sql.DB
	db         database
	err        error
	once       sync.Once
	cleanupErr error
	permit     bool
}

// New executes preparation once, closes its pool, waits for physical disconnect
// and captures a baseline. Failed setup admits no tests and disposes its owners.
// ctx controls setup only; Close is required after a successful New.
func New(ctx context.Context, opts Options) (*Fixture, error) {
	return newFixture(ctx, opts, production())
}
func newFixture(ctx context.Context, opts Options, deps dependencies) (_ *Fixture, err error) {
	if opts.MaxForks < 0 || opts.OperationTimeout < 0 {
		return nil, failure("options", errors.New("MaxForks and OperationTimeout must not be negative"), nil)
	}
	if opts.MaxForks == 0 {
		opts.MaxForks = 2
	}
	if opts.OperationTimeout == 0 {
		opts.OperationTimeout = 120 * time.Second
	}
	ctx, cancel := context.WithTimeout(ctx, opts.OperationTimeout)
	defer cancel()
	source, startErr := deps.start(ctx, opts.DatabaseOptions)
	if startErr != nil {
		var cleanup error
		if source != nil {
			cleanup = source.Close()
		}
		return nil, failure("start", startErr, cleanup)
	}
	// Public Close is always owed, including invalid-but-not-disposed sources.
	// After consumed capture it is idempotent and returns the stored close result.
	defer func() {
		if source != nil {
			_ = source.Close()
		}
	}()
	pool, openErr := deps.open(source.DSN(), 1, 1)
	var base baseline
	stage := "prepare"
	operationErr := openErr
	if pool != nil {
		defer pool.Close() // Also handles a panicking user callback.
		if operationErr == nil {
			operationErr = pool.PingContext(ctx)
		}
		if operationErr == nil && opts.Prepare != nil {
			operationErr = opts.Prepare(ctx, pool, source.DSN())
		}
		if closeErr := pool.Close(); closeErr != nil {
			cleanup := errors.Join(closeErr, source.Close())
			source = nil
			return nil, failure(stage, operationErr, cleanup)
		}
	}
	if operationErr == nil {
		stage = "disconnect"
		operationErr = source.WaitDisconnected(ctx)
	}
	if operationErr == nil {
		stage = "capture"
		base, operationErr = source.capture(ctx)
	}
	sourceErr := source.Close()
	source = nil
	if operationErr != nil || sourceErr != nil {
		cleanup := sourceErr
		if base != nil {
			cleanup = errors.Join(cleanup, base.Close())
		}
		return nil, failure(stage, operationErr, cleanup)
	}
	return &Fixture{opts: opts, deps: deps, base: base, entries: make(map[any]*child), permits: make(chan struct{}, opts.MaxForks), stopped: make(chan struct{})}, nil
}

// DB returns this test's pool, registering cleanup before publishing it. Repeated
// calls with the same testing.TB share that test's pool; distinct subtests get
// distinct children. Call after t.Parallel, and do not hold a parent's child while
// waiting for nested children under an exhausted MaxForks budget.
func (f *Fixture) DB(t testing.TB) *sql.DB {
	t.Helper()
	pool, err := f.get(t.Context(), t, func(c *child) {
		t.Cleanup(func() {
			if err := f.dispose(c); err != nil {
				t.Error(err)
			}
		})
	})
	if err != nil {
		t.Fatal(err)
		return nil
	}
	return pool
}

func (f *Fixture) get(ctx context.Context, key any, register func(*child)) (*sql.DB, error) {
	ctx, cancel := context.WithTimeout(ctx, f.opts.OperationTimeout)
	defer cancel()
	f.mu.Lock()
	if f.closed || f.debt != nil {
		debt := f.debt
		f.mu.Unlock()
		return nil, failure("acquire", mariamem.ErrClosed, debt)
	}
	if existing := f.entries[key]; existing != nil {
		f.mu.Unlock()
		select {
		case <-existing.ready:
			return existing.pool, existing.err
		case <-ctx.Done():
			return nil, failure("acquire", ctx.Err(), nil)
		}
	}
	c := &child{ready: make(chan struct{})}
	f.entries[key] = c
	f.starting.Add(1)
	f.mu.Unlock()
	defer f.starting.Done()
	defer close(c.ready)
	var err error
	select {
	case f.permits <- struct{}{}:
		c.permit = true
	case <-ctx.Done():
		err = ctx.Err()
	case <-f.stopped:
		err = mariamem.ErrClosed
	}
	if err == nil {
		f.mu.Lock()
		if f.closed || f.debt != nil {
			err = errors.Join(mariamem.ErrClosed, f.debt)
		}
		f.mu.Unlock()
	}
	if err == nil {
		err = ctx.Err()
	}
	if err == nil {
		c.db, err = f.base.fork(ctx)
	}
	if err == nil {
		c.pool, err = f.deps.open(c.db.DSN(), 2, 1)
	}
	if err == nil {
		err = c.pool.PingContext(ctx)
	}
	if err == nil {
		f.mu.Lock()
		if f.closed || f.debt != nil {
			err = errors.Join(mariamem.ErrClosed, f.debt)
		}
		f.mu.Unlock()
	}
	if err != nil {
		cleanup := f.dispose(c)
		if cleanup == nil {
			f.mu.Lock()
			cleanup = f.debt
			f.mu.Unlock()
		}
		c.pool = nil
		c.err = failure("acquire", err, cleanup)
		return nil, c.err
	}
	register(c)
	return c.pool, nil
}

func (f *Fixture) dispose(c *child) error {
	c.once.Do(func() {
		var poolErr, dbErr error
		if c.pool != nil {
			poolErr = c.pool.Close()
		}
		if c.db != nil {
			dbErr = c.db.Close()
		}
		c.cleanupErr = errors.Join(poolErr, dbErr)
		if c.cleanupErr != nil {
			f.mu.Lock()
			f.debt = errors.Join(f.debt, c.cleanupErr)
			f.stopLocked()
			f.mu.Unlock()
		} else if c.permit {
			<-f.permits
		}
	})
	if c.cleanupErr != nil {
		return failure("cleanup", nil, c.cleanupErr)
	}
	return nil
}

// stopLocked wakes queued acquisitions as well as rejecting new callers.
func (f *Fixture) stopLocked() {
	if !f.closed {
		f.closed = true
		close(f.stopped)
	}
}

// Close stops admission and actively closes pools, children, then the baseline.
// It is idempotent and returns the stored result. Cleanup does not use a canceled
// test context. Underlying noncooperative guest operations can outlast deadlines.
func (f *Fixture) Close() error {
	f.closeOnce.Do(func() {
		f.mu.Lock()
		f.stopLocked()
		f.mu.Unlock()
		f.starting.Wait()
		for _, c := range f.entries {
			f.closeErr = errors.Join(f.closeErr, f.dispose(c))
		}
		if err := f.base.Close(); err != nil {
			f.closeErr = errors.Join(f.closeErr, failure("baseline cleanup", nil, err))
		}
	})
	return f.closeErr
}

// Run supplies TestMain integration. install assigns the fixture used by tests.
// Failed setup skips m.Run; cleanup failure turns a zero suite exit into one.
// Existing nonzero suite exit codes are preserved. Call os.Exit with the result.
func Run(m *testing.M, opts Options, install func(*Fixture)) int {
	return run(context.Background(), opts, install, m.Run, os.Stderr, production())
}
func run(ctx context.Context, opts Options, install func(*Fixture), suite func() int, out io.Writer, deps dependencies) (code int) {
	f, err := newFixture(ctx, opts, deps)
	if err != nil {
		fmt.Fprintln(out, err)
		return 1
	}
	defer func() {
		if err := f.Close(); err != nil {
			fmt.Fprintln(out, err)
			if code == 0 {
				code = 1
			}
		}
	}()
	install(f)
	return suite()
}
