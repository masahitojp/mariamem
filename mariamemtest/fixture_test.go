package mariamemtest

import (
	"bytes"
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"fmt"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

type journal struct {
	sync.Mutex
	events []string
}

func (j *journal) add(s string) { j.Lock(); defer j.Unlock(); j.events = append(j.events, s) }
func (j *journal) count(s string) int {
	j.Lock()
	defer j.Unlock()
	n := 0
	for _, v := range j.events {
		if v == s {
			n++
		}
	}
	return n
}
func (j *journal) text() string { j.Lock(); defer j.Unlock(); return strings.Join(j.events, ",") }

type fakeDB struct {
	name      string
	j         *journal
	closed    bool
	invalid   bool
	closeErr  error
	waitErr   error
	captureFn func(context.Context) (baseline, error)
}

func (d *fakeDB) DSN() string { return d.name }
func (d *fakeDB) Close() error {
	if !d.closed {
		d.closed = true
		d.j.add(d.name + ".dispose")
	}
	return d.closeErr
}
func (d *fakeDB) WaitDisconnected(context.Context) error {
	d.j.add(d.name + ".drain")
	return d.waitErr
}
func (d *fakeDB) capture(ctx context.Context) (baseline, error) {
	d.j.add(d.name + ".capture")
	return d.captureFn(ctx)
}

type fakeBase struct {
	mu       sync.Mutex
	j        *journal
	n        int
	closed   int
	closeErr error
	forkFn   func(context.Context) (database, error)
}

func (b *fakeBase) fork(ctx context.Context) (database, error) {
	b.mu.Lock()
	b.n++
	n := b.n
	b.mu.Unlock()
	if b.forkFn != nil {
		return b.forkFn(ctx)
	}
	return &fakeDB{name: fmt.Sprintf("child%d", n), j: b.j}, nil
}
func (b *fakeBase) Close() error { b.closed++; b.j.add("baseline.close"); return b.closeErr }

type connector struct {
	j                 *journal
	name              string
	pingErr, closeErr error
}

func (c connector) Connect(context.Context) (driver.Conn, error) { return connection{c}, nil }
func (c connector) Driver() driver.Driver                        { return fakeDriver{} }

type fakeDriver struct{}

func (fakeDriver) Open(string) (driver.Conn, error) { return nil, errors.New("unexpected driver Open") }

type connection struct{ c connector }

func (c connection) Prepare(string) (driver.Stmt, error) {
	return nil, errors.New("unexpected SQL in component test")
}
func (c connection) Begin() (driver.Tx, error)  { return nil, errors.New("unexpected transaction") }
func (c connection) Ping(context.Context) error { return c.c.pingErr }
func (c connection) Close() error               { c.c.j.add(c.c.name + ".pool.close"); return c.c.closeErr }

func environment() (dependencies, *fakeDB, *fakeBase, *journal) {
	j := &journal{}
	b := &fakeBase{j: j}
	d := &fakeDB{name: "source", j: j}
	d.captureFn = func(context.Context) (baseline, error) { _ = d.Close(); return b, nil }
	deps := dependencies{
		start: func(context.Context, mariamem.Options) (database, error) { j.add("start"); return d, nil },
		open: func(name string, maxOpen, maxIdle int) (*sql.DB, error) {
			j.add(fmt.Sprintf("%s.pool.%d.%d", name, maxOpen, maxIdle))
			p := sql.OpenDB(connector{j: j, name: name})
			p.SetMaxOpenConns(maxOpen)
			p.SetMaxIdleConns(maxIdle)
			return p, nil
		},
	}
	return deps, d, b, j
}
func mustFixture(t *testing.T, deps dependencies, opts Options) *Fixture {
	t.Helper()
	f, err := newFixture(t.Context(), opts, deps)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := f.Close(); err != nil {
			t.Error(err)
		}
	})
	return f
}

func TestPrepareCaptureAndTestOwnership(t *testing.T) {
	deps, source, base, j := environment()
	prepared := 0
	f := mustFixture(t, deps, Options{Prepare: func(ctx context.Context, p *sql.DB, dsn string) error {
		prepared++
		if dsn != "source" || p.Stats().MaxOpenConnections != 1 {
			t.Fatal("wrong preparation target/budget")
		}
		j.add("prepare")
		return nil
	}})
	if prepared != 1 || !source.closed {
		t.Fatal("preparation/capture lifecycle")
	}
	if got := j.text(); got != "start,source.pool.1.1,prepare,source.pool.close,source.drain,source.capture,source.dispose" {
		t.Fatal(got)
	}
	p := f.DB(t)
	if p != f.DB(t) || p.Stats().MaxOpenConnections != 2 {
		t.Fatal("same test must reuse its bounded pool")
	}
	if err := f.Close(); err != nil {
		t.Fatal(err)
	}
	if err := p.Ping(); err == nil {
		t.Fatal("explicit fixture Close left pool usable")
	}
	if base.closed != 1 || j.count("child1.dispose") != 1 || j.count("child1.pool.close") != 1 {
		t.Fatal(j.text())
	}
	if !strings.HasSuffix(j.text(), "child1.pool.close,child1.dispose,baseline.close") {
		t.Fatal(j.text())
	}
	if _, err := f.get(t.Context(), "after close", func(*child) {}); !errors.Is(err, mariamem.ErrClosed) {
		t.Fatal(err)
	}
}

func TestCaptureFailureOwnership(t *testing.T) {
	for _, kind := range []string{"preserved", "consumed", "invalid", "partial"} {
		t.Run(kind, func(t *testing.T) {
			deps, d, b, j := environment()
			original := errors.New("capture rejected")
			d.captureFn = func(context.Context) (baseline, error) {
				switch kind {
				case "consumed":
					_ = d.Close()
				case "invalid":
					d.invalid = true // Invalid does not mean physically disposed.
				case "partial":
					_ = d.Close()
					_ = b.Close() // Root capture owns partial backing unwind.
				case "preserved":
					if d.closed {
						t.Fatal("source already disposed at rejection")
					}
				}
				return nil, original
			}
			f, err := newFixture(t.Context(), Options{}, deps)
			if f != nil || !errors.Is(err, original) || !d.closed || j.count("source.dispose") != 1 {
				t.Fatalf("fixture=%v err=%v events=%s", f, err, j.text())
			}
			want := 0
			if kind == "partial" {
				want = 1
			}
			if b.closed != want {
				t.Fatal("partial backing released twice or lost")
			}
		})
	}
}

func TestSetupFailuresKeepCauseAndCleanup(t *testing.T) {
	for _, stage := range []string{"start", "open", "ping", "prepare", "disconnect", "capture", "source cleanup"} {
		t.Run(stage, func(t *testing.T) {
			deps, d, b, j := environment()
			original := errors.New("original")
			cleanup := errors.New("dispose failed")
			d.closeErr = cleanup
			opts := Options{}
			switch stage {
			case "start":
				deps.start = func(context.Context, mariamem.Options) (database, error) { return d, original }
			case "open":
				deps.open = func(string, int, int) (*sql.DB, error) { return nil, original }
			case "ping":
				deps.open = func(name string, a, z int) (*sql.DB, error) {
					return sql.OpenDB(connector{j: j, name: name, pingErr: original}), nil
				}
			case "prepare":
				opts.Prepare = func(context.Context, *sql.DB, string) error { return original }
			case "disconnect":
				d.waitErr = original
			case "capture":
				d.captureFn = func(context.Context) (baseline, error) { return nil, original }
			case "source cleanup":
				original = cleanup
			}
			f, err := newFixture(t.Context(), opts, deps)
			if f != nil || !errors.Is(err, original) || !errors.Is(err, cleanup) || j.count("source.dispose") != 1 {
				t.Fatalf("%v %s", err, j.text())
			}
			var detail *Error
			if !errors.As(err, &detail) || !strings.Contains(detail.CleanupState, "unconfirmed") {
				t.Fatal(err)
			}
			want := 0
			if stage == "source cleanup" {
				want = 1
			}
			if b.closed != want {
				t.Fatal("baseline owner escaped failure")
			}
		})
	}
}

func TestPreparationPanicStillDisposes(t *testing.T) {
	deps, _, _, j := environment()
	func() {
		defer func() {
			if recover() != "callback panic" {
				t.Fatal("panic lost")
			}
		}()
		_, _ = newFixture(t.Context(), Options{Prepare: func(context.Context, *sql.DB, string) error { panic("callback panic") }}, deps)
	}()
	if !strings.HasSuffix(j.text(), "source.pool.close,source.dispose") {
		t.Fatal(j.text())
	}
}

func TestBoundedAdmissionAndCancellation(t *testing.T) {
	deps, _, b, _ := environment()
	f := mustFixture(t, deps, Options{MaxForks: 2, OperationTimeout: time.Second})
	var owners []*child
	register := func(c *child) { owners = append(owners, c) }
	for _, key := range []string{"a", "b"} {
		if _, err := f.get(t.Context(), key, register); err != nil {
			t.Fatal(err)
		}
	}
	ctx, cancel := context.WithTimeout(t.Context(), 100*time.Millisecond)
	defer cancel()
	if _, err := f.get(ctx, "blocked", register); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatal(err)
	}
	if b.n != 2 || len(f.permits) != 2 {
		t.Fatalf("started beyond cap: %d", b.n)
	}
	if err := f.dispose(owners[0]); err != nil {
		t.Fatal(err)
	}
	if _, err := f.get(t.Context(), "replacement", register); err != nil {
		t.Fatal(err)
	}
	if b.n != 3 || len(f.permits) != 2 {
		t.Fatal("permit not returned after confirmed cleanup")
	}
}

func TestChildPoolConstructionFailures(t *testing.T) {
	for _, stage := range []string{"fork", "open", "ping"} {
		t.Run(stage, func(t *testing.T) {
			deps, _, b, j := environment()
			original := errors.New("child " + stage + " failed")
			b.forkFn = func(context.Context) (database, error) {
				if stage == "fork" {
					return nil, original
				}
				return &fakeDB{name: "child", j: j}, nil
			}
			open := deps.open
			deps.open = func(name string, a, z int) (*sql.DB, error) {
				if name == "source" {
					return open(name, a, z)
				}
				if stage == "open" {
					return nil, original
				}
				return sql.OpenDB(connector{j: j, name: name, pingErr: original}), nil
			}
			f := mustFixture(t, deps, Options{MaxForks: 1})
			if _, err := f.get(t.Context(), "failed", func(*child) { t.Fatal("registered failed child") }); !errors.Is(err, original) {
				t.Fatal(err)
			}
			if len(f.permits) != 0 {
				t.Fatal("successful disposal lost permit")
			}
			if stage != "fork" && j.count("child.dispose") != 1 {
				t.Fatal(j.text())
			}
			if err := f.Close(); err != nil {
				t.Fatal(err)
			}
		})
	}
}

func TestPoolCleanupFailureStillClosesChildAndKeepsBothErrors(t *testing.T) {
	deps, _, b, j := environment()
	poolErr, childErr := errors.New("pool close failed"), errors.New("child close failed")
	b.forkFn = func(context.Context) (database, error) { return &fakeDB{name: "child", j: j, closeErr: childErr}, nil }
	open := deps.open
	deps.open = func(name string, a, z int) (*sql.DB, error) {
		if name == "source" {
			return open(name, a, z)
		}
		return sql.OpenDB(connector{j: j, name: name, closeErr: poolErr}), nil
	}
	f, err := newFixture(t.Context(), Options{}, deps)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = f.get(t.Context(), "a", func(*child) {}); err != nil {
		t.Fatal(err)
	}
	err = f.Close()
	if !errors.Is(err, poolErr) || !errors.Is(err, childErr) || !strings.HasSuffix(j.text(), "child.pool.close,child.dispose,baseline.close") {
		t.Fatal(err, j.text())
	}
	if !errors.Is(f.Close(), poolErr) || j.count("child.dispose") != 1 {
		t.Fatal("cleanup error lost on repeated Close")
	}
}

func TestCloseUnblocksWaitingAdmission(t *testing.T) {
	deps, _, b, _ := environment()
	f := mustFixture(t, deps, Options{MaxForks: 1})
	if _, err := f.get(t.Context(), "a", func(*child) {}); err != nil {
		t.Fatal(err)
	}
	waiting := make(chan error, 1)
	go func() { _, err := f.get(t.Context(), "b", func(*child) {}); waiting <- err }()
	if err := f.Close(); err != nil {
		t.Fatal(err)
	}
	if err := <-waiting; !errors.Is(err, mariamem.ErrClosed) {
		t.Fatal(err)
	}
	if b.n != 1 {
		t.Fatal("waiting admission started another guest")
	}
}

func TestConcurrentSameOwnerAndEarlyClose(t *testing.T) {
	deps, _, b, j := environment()
	f := mustFixture(t, deps, Options{})
	entered, release := make(chan struct{}), make(chan struct{})
	b.forkFn = func(context.Context) (database, error) {
		close(entered)
		<-release
		return &fakeDB{name: "slow", j: j}, nil
	}
	var wg sync.WaitGroup
	var mu sync.Mutex
	registrations := 0
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = f.get(t.Context(), "same", func(*child) { mu.Lock(); registrations++; mu.Unlock() })
		}()
	}
	<-entered
	closed := make(chan error, 1)
	go func() { closed <- f.Close() }()
	<-f.stopped
	close(release)
	wg.Wait()
	if err := <-closed; err != nil {
		t.Fatal(err)
	}
	if b.n != 1 || registrations != 0 || j.count("slow.dispose") != 1 {
		t.Fatalf("forks=%d registrations=%d events=%s", b.n, registrations, j.text())
	}
}

func TestChildFailureAndCleanupDebtStopAdmission(t *testing.T) {
	deps, _, b, j := environment()
	original := errors.New("ping failed")
	cleanup := errors.New("child did not stop")
	b.forkFn = func(context.Context) (database, error) {
		return &fakeDB{name: "child", j: j, closeErr: cleanup}, original
	}
	f, err := newFixture(t.Context(), Options{MaxForks: 1}, deps)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = f.get(t.Context(), "a", func(*child) { t.Fatal("failed child admitted") }); !errors.Is(err, original) || !errors.Is(err, cleanup) {
		t.Fatal(err)
	}
	if len(f.permits) != 1 {
		t.Fatal("unconfirmed disposal released permit")
	}
	if _, err = f.get(t.Context(), "b", func(*child) {}); !errors.Is(err, cleanup) || b.n != 1 {
		t.Fatal("cleanup debt admitted another child", err)
	}
	if err = f.Close(); !errors.Is(err, cleanup) || j.count("child.dispose") != 1 || b.closed != 1 {
		t.Fatal(err, j.text())
	}
}

func TestRunExitAndNoAdmission(t *testing.T) {
	for _, exit := range []int{0, 7} {
		for _, cleanupFails := range []bool{false, true} {
			t.Run(fmt.Sprintf("%d/%v", exit, cleanupFails), func(t *testing.T) {
				deps, _, base, _ := environment()
				cleanup := errors.New("baseline removal failed")
				if cleanupFails {
					base.closeErr = cleanup
				}
				var out bytes.Buffer
				installed := false
				code := run(t.Context(), Options{}, func(*Fixture) { installed = true }, func() int { return exit }, &out, deps)
				want := exit
				if want == 0 && cleanupFails {
					want = 1
				}
				if code != want || !installed || base.closed != 1 || (cleanupFails && !strings.Contains(out.String(), cleanup.Error())) {
					t.Fatal(code, out.String())
				}
			})
		}
	}
	deps, d, _, _ := environment()
	d.waitErr = errors.New("active preparation client")
	var out bytes.Buffer
	code := run(t.Context(), Options{}, func(*Fixture) { t.Fatal("install after failed setup") }, func() int { t.Fatal("suite after failed setup"); return 0 }, &out, deps)
	if code != 1 || !strings.Contains(out.String(), "active preparation client") {
		t.Fatal(code, out.String())
	}
}

func TestNegativeOptionsAndDefaults(t *testing.T) {
	for _, opts := range []Options{{MaxForks: -1}, {OperationTimeout: -1}} {
		deps, _, _, j := environment()
		if f, err := newFixture(t.Context(), opts, deps); f != nil || err == nil || j.count("start") != 0 {
			t.Fatal("invalid options started a guest")
		}
	}
	deps, _, _, _ := environment()
	f := mustFixture(t, deps, Options{})
	if cap(f.permits) != 2 || f.opts.OperationTimeout != 120*time.Second {
		t.Fatal("defaults changed")
	}
}
