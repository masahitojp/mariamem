package mariamemtest

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

// An explicitly registered, cooperative job fixture. The entry cannot discover
// unregistered future jobs; the fixture hook supplies that application boundary.
type httpJobApp struct {
	mu                                  sync.Mutex
	pool                                *sql.DB
	work                                context.Context
	cancel                              context.CancelFunc
	release, started, done, pausedEvent chan struct{}
	releaseOnce, pauseOnce              sync.Once
	paused, active, stopped, skipJoin   bool
	jobErr                              error
	events                              []string
}

func (a *httpJobApp) BaseURL() string  { return "http://127.0.0.1:1" }
func (a *httpJobApp) Identity() string { return "registered-job-owner" }
func (a *httpJobApp) releaseJob()      { a.releaseOnce.Do(func() { close(a.release) }) }
func (a *httpJobApp) record(event string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.events = append(a.events, event)
}
func (a *httpJobApp) canAdmitWork() bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	return !a.paused && !a.stopped
}
func (a *httpJobApp) runJob() {
	var err error
	defer func() {
		a.mu.Lock()
		a.jobErr = err
		a.active = false
		a.events = append(a.events, "job_done")
		a.mu.Unlock()
		close(a.done)
	}()
	tx, e := a.pool.BeginTx(a.work, nil)
	if e != nil {
		err = e
		close(a.started)
		return
	}
	defer tx.Rollback()
	_, err = tx.ExecContext(a.work, "INSERT INTO e2e_job_guard VALUES(2)")
	close(a.started)
	if err != nil {
		return
	}
	select {
	case <-a.release:
		err = tx.Commit()
	case <-a.work.Done():
		err = a.work.Err()
	}
}
func (a *httpJobApp) QuiesceAndRetire(ctx context.Context) error {
	a.mu.Lock()
	a.paused = true
	a.events = append(a.events, "pause")
	a.mu.Unlock()
	a.pauseOnce.Do(func() { close(a.pausedEvent) })
	if a.skipJoin {
		return nil
	} // negative control: transaction/physical session survives
	select {
	case <-a.done:
	case <-ctx.Done():
		return ctx.Err()
	}
	a.mu.Lock()
	err := a.jobErr
	p := a.pool
	a.pool = nil
	a.events = append(a.events, "join")
	a.mu.Unlock()
	if p != nil {
		err = errors.Join(err, p.Close())
	}
	return err
}
func (a *httpJobApp) resume(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	if !a.paused || a.active {
		return errors.New("resume before pause/join")
	}
	a.events = append(a.events, "resume")
	a.paused = false
	return nil
}
func (a *httpJobApp) StopReap(ctx context.Context) error {
	a.mu.Lock()
	a.stopped = true
	a.paused = true
	a.mu.Unlock()
	a.cancel()
	a.releaseJob()
	select {
	case <-a.done:
	case <-ctx.Done():
		return ctx.Err()
	}
	a.mu.Lock()
	p := a.pool
	a.pool = nil
	a.events = append(a.events, "stop")
	a.mu.Unlock()
	if p != nil {
		return p.Close()
	}
	return nil
}

type httpJobObservedLive struct {
	httpLive
	app           *httpJobApp
	requireJoined bool
	resetSeen     bool
}

func (l *httpJobObservedLive) Reset(ctx context.Context, opts mariamem.ResetOptions) error {
	l.app.mu.Lock()
	joined := l.app.paused && !l.app.active
	l.app.events = append(l.app.events, "reset")
	l.app.mu.Unlock()
	l.resetSeen = true
	if l.requireJoined && !joined {
		return errors.New("Reset began before registered job pause/join")
	}
	return l.httpLive.Reset(ctx, opts)
}
func httpRegisteredFixture(t *testing.T, skip bool) (*HTTPFixture, *httpJobApp, *httpJobObservedLive) {
	t.Helper()
	if os.Getenv("E2E_OWNED_RUNTIME") != "1" {
		t.Skip("set E2E_OWNED_RUNTIME=1")
	}
	work, cancel := context.WithCancel(context.Background())
	a := &httpJobApp{work: work, cancel: cancel, release: make(chan struct{}), started: make(chan struct{}), done: make(chan struct{}), pausedEvent: make(chan struct{}), skipJoin: skip}
	// Even construction failure before registration must release this fixture's context.
	t.Cleanup(cancel)
	cfg := HTTPConfig{DrainTimeout: 100 * time.Millisecond,
		Prepare: func(ctx context.Context, db *mariamem.Database) error {
			p, err := httpPhysicalPool(db.ConnectionInfo())
			if err != nil {
				return err
			}
			defer p.Close()
			for _, s := range []string{"CREATE TABLE e2e_job_guard(v INT PRIMARY KEY)", "INSERT INTO e2e_job_guard VALUES(1)"} {
				if _, err = p.ExecContext(ctx, s); err != nil {
					return err
				}
			}
			return nil
		},
		StartReady: func(ctx context.Context, info mariamem.ConnectionInfo, register func(HTTPApp) error) (HTTPApp, error) {
			p, err := httpPhysicalPool(info)
			if err != nil {
				return nil, err
			}
			a.pool = p
			if err = register(a); err != nil {
				_ = p.Close()
				return nil, err
			}
			a.mu.Lock()
			a.active = true
			a.events = append(a.events, "job_start")
			a.mu.Unlock()
			go a.runJob()
			select {
			case <-a.started:
			case <-ctx.Done():
				return nil, ctx.Err()
			}
			a.mu.Lock()
			err = a.jobErr
			a.mu.Unlock()
			return a, err
		},
		Resume: func(ctx context.Context, app HTTPApp) error { return app.(*httpJobApp).resume(ctx) },
	}
	f, err := newHTTP(cfg, startHTTP)
	if f != nil {
		t.Cleanup(func() {
			a.releaseJob()
			if e := f.close(); e != nil {
				t.Error(e)
			}
		})
	}
	if err != nil {
		t.Fatal(err)
	}
	observed := &httpJobObservedLive{httpLive: f.owners.live, app: a, requireJoined: !skip}
	f.owners.live = observed
	return f, a, observed
}
func httpJobSetup(t *testing.T, f *HTTPFixture, a *httpJobApp) (*HTTPCase, <-chan struct{}, *error) {
	t.Helper()
	c, err := f.reserve()
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	done := make(chan struct{})
	var result error
	t.Cleanup(func() {
		a.releaseJob()
		cancel()
		select {
		case <-done:
			if err := c.finish(); err != nil {
				t.Error(err)
			}
		case <-time.After(10 * time.Second):
			t.Error("setup did not join; leave owner unconfirmed")
		}
	})
	go func() { result = c.setup(ctx); close(done) }()
	return c, done, &result
}
func TestHTTPPhysicalRegisteredJobJoinsBeforeReset(t *testing.T) {
	f, a, observed := httpRegisteredFixture(t, false)
	c, done, result := httpJobSetup(t, f, a)
	select {
	case <-a.pausedEvent:
	case <-time.After(5 * time.Second):
		t.Fatal("hook did not pause")
	}
	if a.canAdmitWork() {
		t.Fatal("new registered work admitted while paused")
	}
	// A transaction is still held. The setup must wait for its actual completion;
	// merely observing a hook invocation cannot count as a join.
	select {
	case <-done:
		t.Fatal("setup returned while job transaction was held")
	default:
	}
	if f.owners.live.Status().Generation != 0 {
		t.Fatal("Reset occurred before job release")
	}
	a.releaseJob()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("setup did not finish")
	}
	if *result != nil {
		t.Fatal(*result)
	}
	if !observed.resetSeen || !a.canAdmitWork() {
		t.Fatal("Reset/Resume missing")
	}
	pool, err := httpPhysicalPool(f.target)
	if err != nil {
		t.Fatal(err)
	}
	if err = c.Register(pool); err != nil {
		_ = pool.Close()
		t.Fatal(err)
	}
	var count int
	if err = pool.QueryRow("SELECT COUNT(*) FROM e2e_job_guard").Scan(&count); err != nil || count != 1 {
		t.Fatalf("old committed job data leaked: %d %v", count, err)
	}
	if err = c.finish(); err != nil {
		t.Fatal(err)
	}
	a.mu.Lock()
	events := append([]string(nil), a.events...)
	a.mu.Unlock()
	index := func(name string) int {
		for i, event := range events {
			if event == name {
				return i
			}
		}
		return -1
	}
	if !(index("pause") < index("job_done") && index("job_done") < index("join") && index("join") < index("reset") && index("reset") < index("resume")) {
		t.Fatal("wrong hook/job order", events)
	}
	t.Log("registered job pause -> actual transaction join -> physical retirement -> Reset -> Resume; seed restored", events)
}
func TestHTTPPhysicalUnjoinedJobRejectedByDrain(t *testing.T) {
	f, a, observed := httpRegisteredFixture(t, true)
	c, done, result := httpJobSetup(t, f, a)
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("busy setup did not finish")
	}
	if !errors.Is(*result, mariamem.ErrBusy) {
		t.Fatalf("unjoined transaction not rejected: %v", *result)
	}
	if !observed.resetSeen || f.owners.live.Status().Generation != 0 {
		t.Fatal("busy Reset altered backend")
	}
	if err := c.finish(); err != nil {
		t.Fatal(err)
	}
	if _, err := f.reserve(); err == nil {
		t.Fatal("later body could start after failed setup")
	}
	a.mu.Lock()
	for _, event := range a.events {
		if event == "resume" {
			t.Error("Resume after failed Reset")
		}
	}
	a.mu.Unlock()
	a.releaseJob()
	// Ownership is still registered; StopReap cancels/joins and then retires pool.
	if err := f.close(); err != nil {
		t.Fatal(err)
	}
	t.Log("lying join hook hit actual physical-session drain; no generation commit, Resume or later admission")
}
