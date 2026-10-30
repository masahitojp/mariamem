// Package mariamemtest provides owned test entries for mariamem.
package mariamemtest

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"reflect"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

// HTTPApp owns application work and physical SQL sessions. Hooks cooperate with
// ctx, join their work before returning, and report unconfirmed cleanup as error.
type HTTPApp interface {
	BaseURL() string
	Identity() string
	QuiesceAndRetire(context.Context) error
	StopReap(context.Context) error
}

// HTTPConfig declares one sequential HTTP fixture owner. Preparation closes all
// its SQL sessions before returning. Register partial apps before readiness can
// fail; return the same registered ready handle. No output/log capture is added.
type HTTPConfig struct {
	Options                                                  mariamem.Options
	Prepare                                                  func(context.Context, *mariamem.Database) error
	StartReady                                               func(context.Context, mariamem.ConnectionInfo, func(HTTPApp) error) (HTTPApp, error)
	SoleWorkSource                                           bool
	Resume                                                   func(context.Context, HTTPApp) error
	ExternalState                                            func(context.Context, HTTPApp, func(io.Closer) error) error
	SetupTimeout, ResetTimeout, DrainTimeout, CleanupTimeout time.Duration
}

// HTTPPanic preserves a hook panic and an additional cleanup failure.
type HTTPPanic struct {
	Value   any
	Cleanup error
}

func (p *HTTPPanic) Error() string {
	return fmt.Sprintf("E2E panic: %v; cleanup: %v", p.Value, p.Cleanup)
}
func httpCleanupCall(fn func() error) (err error) {
	defer func() {
		if value := recover(); value != nil {
			err = &HTTPPanic{Value: value}
		}
	}()
	return fn()
}

// HTTPEntryError retains the original cause and readable entry state.
type HTTPEntryError struct {
	Stage, Admission, Cleanup string
	Cause                     error
}

func (e *HTTPEntryError) Error() string {
	return fmt.Sprintf("E2E %s; admission=%s; cleanup=%s: inspect cause and close owner before retrying: %v", e.Stage, e.Admission, e.Cleanup, e.Cause)
}
func (e *HTTPEntryError) Unwrap() error { return e.Cause }
func httpFailure(stage string, cause error) error {
	return &HTTPEntryError{stage, "stopped", "not-confirmed", cause}
}
func (c HTTPConfig) defaults() (HTTPConfig, error) {
	if c.Prepare == nil || c.StartReady == nil {
		return c, errors.New("Prepare and StartReady required")
	}
	if c.Resume == nil && !c.SoleWorkSource {
		return c, errors.New("declare SoleWorkSource or supply Resume")
	}
	for _, d := range []struct {
		p        *time.Duration
		fallback time.Duration
	}{
		{&c.SetupTimeout, 120 * time.Second}, {&c.ResetTimeout, 120 * time.Second}, {&c.DrainTimeout, 5 * time.Second}, {&c.CleanupTimeout, 30 * time.Second},
	} {
		if *d.p < 0 {
			return c, errors.New("timeouts must not be negative")
		}
		if *d.p == 0 {
			*d.p = d.fallback
		}
	}
	return c, nil
}

type httpLive interface {
	ConnectionInfo() mariamem.ConnectionInfo
	Status() mariamem.LiveStatus
	Reset(context.Context, mariamem.ResetOptions) error
	Close() error
}
type httpOwners struct {
	source, baseline io.Closer
	live             httpLive
}
type httpFactory func(context.Context, HTTPConfig, *httpOwners) error

func startHTTP(ctx context.Context, c HTTPConfig, o *httpOwners) error {
	db, err := mariamem.Start(ctx, c.Options)
	if db != nil {
		o.source = db
	}
	if err != nil {
		return err
	}
	if err = c.Prepare(ctx, db); err != nil {
		return err
	}
	if err = ctx.Err(); err != nil {
		return err
	}
	if err = db.WaitDisconnected(ctx); err != nil {
		return err
	}
	saved, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if saved != nil {
		o.baseline = saved
	}
	if err != nil {
		return err
	}
	live, err := saved.Live(ctx)
	if live != nil {
		o.live = live
	}
	return err
}

// HTTPFixture owns preparation, Live and app cleanup. Do not copy. Create it on
// a parent test common to every Case. Cases sharing an owner are sequential;
// parallel tests must create independent fixture owners.
type HTTPFixture struct {
	config                 HTTPConfig
	mu                     sync.Mutex
	owners                 httpOwners
	apps                   []HTTPApp
	app                    HTTPApp
	target                 mariamem.ConnectionInfo
	identity               string
	active, failed, closed bool
	closeErr               error
}

func nilHTTP(v any) bool {
	if v == nil {
		return true
	}
	switch reflect.ValueOf(v).Kind() {
	case reflect.Pointer, reflect.Map, reflect.Slice, reflect.Func, reflect.Chan, reflect.Interface:
		return reflect.ValueOf(v).IsNil()
	}
	return false
}
func sameHTTP(a, b HTTPApp) bool {
	return reflect.TypeOf(a) == reflect.TypeOf(b) && reflect.TypeOf(a).Comparable() && a == b
}
func (f *HTTPFixture) register(app HTTPApp) error {
	if nilHTTP(app) || !reflect.TypeOf(app).Comparable() {
		return errors.New("app must be a non-nil comparable handle")
	}
	for _, a := range f.apps {
		if sameHTTP(a, app) {
			return errors.New("duplicate app registration")
		}
	}
	f.apps = append(f.apps, app)
	return nil
}
func newHTTP(c HTTPConfig, factory httpFactory, onOwned ...func(*HTTPFixture)) (*HTTPFixture, error) {
	c, err := c.defaults()
	if err != nil {
		return nil, err
	}
	f := &HTTPFixture{config: c}
	for _, register := range onOwned {
		register(f)
	}
	defer func() {
		if primary := recover(); primary != nil {
			cleanup := f.close()
			if cleanup != nil {
				panic(&HTTPPanic{Value: primary, Cleanup: cleanup})
			}
			panic(primary)
		}
	}()
	ctx, cancel := context.WithTimeout(context.Background(), c.SetupTimeout)
	defer cancel()
	fail := func(stage string, err error) (*HTTPFixture, error) {
		f.failed = true
		return f, errors.Join(httpFailure(stage, err), f.close())
	}
	if err = factory(ctx, c, &f.owners); err != nil {
		return fail("prepare", err)
	}
	if f.owners.live == nil {
		return fail("live", errors.New("missing Live"))
	}
	f.target = f.owners.live.ConnectionInfo()
	f.app, err = c.StartReady(ctx, f.target, f.register)
	if err != nil {
		return fail("start_ready", err)
	}
	if err = ctx.Err(); err != nil {
		return fail("start_ready", err)
	}
	registered := false
	for _, a := range f.apps {
		if sameHTTP(a, f.app) {
			registered = true
		}
	}
	if !registered {
		return fail("start_ready", errors.New("ready app not registered"))
	}
	f.identity = f.app.Identity()
	u, err := url.Parse(f.app.BaseURL())
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") || f.identity == "" {
		return fail("identity", errors.New("app requires identity and HTTP BaseURL"))
	}
	return f, nil
}

// NewHTTP registers parent cleanup before admitting any case. App logs remain
// caller-owned and must be bounded by the supplied startup hook.
func NewHTTP(t *testing.T, c HTTPConfig) *HTTPFixture {
	t.Helper()
	f, err := newHTTP(c, startHTTP, func(f *HTTPFixture) {
		t.Cleanup(func() {
			if e := f.close(); e != nil {
				t.Error(e)
			}
		})
	})
	if err != nil {
		t.Fatal(err)
	}
	return f
}

// HTTPCase owns the exclusive lease, client transport and registered work. Add
// work with Register immediately after creation, before it can fail. Close must
// join that work. Client requests belong to the case; response bodies must close.
type HTTPCase struct {
	BaseURL   string
	Client    *http.Client
	App       HTTPApp
	owner     *HTTPFixture
	resources []io.Closer
	mu        sync.Mutex
	finished  bool
	finishErr error
	work      sync.WaitGroup
	workCtx   context.Context
	cancel    context.CancelFunc
	done      chan struct{}
}

func (c *HTTPCase) Register(resource io.Closer) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.finished || nilHTTP(resource) {
		return errors.New("case closed or invalid resource")
	}
	// Comparable handles permit duplicate detection without calling user methods.
	for _, r := range c.resources {
		if reflect.TypeOf(r) == reflect.TypeOf(resource) && reflect.TypeOf(r).Comparable() && r == resource {
			return errors.New("duplicate case resource")
		}
	}
	c.resources = append(c.resources, resource)
	return nil
}
func (f *HTTPFixture) reserve() (*HTTPCase, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.closed || f.failed {
		return nil, httpFailure("admission", errors.New("owner stopped"))
	}
	if f.active {
		return nil, &HTTPEntryError{"overlap", "rejected", "not-attempted", errors.New("one active case per owner")}
	}
	f.active = true
	ctx, cancel := context.WithCancel(context.Background())
	return &HTTPCase{owner: f, App: f.app, BaseURL: f.app.BaseURL(), workCtx: ctx, cancel: cancel, done: make(chan struct{})}, nil
}
func (c *HTTPCase) setup(parent context.Context) error {
	f := c.owner
	ctx, cancel := context.WithTimeout(parent, f.config.SetupTimeout)
	defer cancel()
	fail := func(stage string, err error) error {
		f.mu.Lock()
		f.failed = true
		f.mu.Unlock()
		return httpFailure(stage, err)
	}
	if err := f.app.QuiesceAndRetire(ctx); err != nil {
		return fail("quiesce", err)
	}
	if err := ctx.Err(); err != nil {
		return fail("quiesce", err)
	}
	before := f.owners.live.Status()
	resetCtx, resetCancel := context.WithTimeout(ctx, f.config.ResetTimeout)
	err := f.owners.live.Reset(resetCtx, mariamem.ResetOptions{DrainTimeout: f.config.DrainTimeout})
	resetCancel()
	if err != nil {
		return fail("reset", err)
	}
	after := f.owners.live.Status()
	if after.State != "ready" || after.Generation != before.Generation+1 || f.owners.live.ConnectionInfo() != f.target || f.app.Identity() != f.identity {
		return fail("identity", errors.New("app or Live identity changed"))
	}
	if err := ctx.Err(); err != nil {
		return fail("reset", err)
	}
	if f.config.Resume != nil {
		if err := f.config.Resume(ctx, f.app); err != nil {
			return fail("resume", err)
		}
	}
	if err := ctx.Err(); err != nil {
		return fail("resume", err)
	}
	if f.config.ExternalState != nil {
		if err := f.config.ExternalState(ctx, f.app, c.Register); err != nil {
			return fail("external_state", err)
		}
	}
	if err := ctx.Err(); err != nil {
		return fail("external_state", err)
	}
	transport := &http.Transport{Proxy: http.ProxyFromEnvironment, DialContext: (&net.Dialer{Timeout: f.config.SetupTimeout, KeepAlive: 30 * time.Second}).DialContext, ForceAttemptHTTP2: true, TLSHandshakeTimeout: f.config.SetupTimeout, ResponseHeaderTimeout: f.config.SetupTimeout, IdleConnTimeout: 30 * time.Second}
	c.Client = &http.Client{Transport: &httpTrackedTransport{transport, c}, Timeout: f.config.SetupTimeout}
	c.resources = append(c.resources, httpCloseFunc(func() error { transport.CloseIdleConnections(); return nil }))
	return nil
}

type httpCloseFunc func() error

func (fn httpCloseFunc) Close() error { return fn() }

type httpTrackedTransport struct {
	base *http.Transport
	c    *HTTPCase
}
type httpTrackedBody struct {
	io.ReadCloser
	once sync.Once
	done func()
}

func (b *httpTrackedBody) Close() error { err := b.ReadCloser.Close(); b.once.Do(b.done); return err }
func (b *httpTrackedBody) Read(p []byte) (int, error) {
	n, err := b.ReadCloser.Read(p)
	if err != nil {
		b.once.Do(b.done)
	}
	return n, err
}
func (tr *httpTrackedTransport) RoundTrip(r *http.Request) (*http.Response, error) {
	c := tr.c
	c.mu.Lock()
	if c.finished {
		c.mu.Unlock()
		return nil, errors.New("E2E case finished")
	}
	c.work.Add(1)
	c.mu.Unlock()
	ctx, cancel := context.WithCancel(r.Context())
	stop := context.AfterFunc(c.workCtx, cancel)
	done := func() { stop(); cancel(); c.work.Done() }
	response, err := tr.base.RoundTrip(r.Clone(ctx))
	if err != nil {
		done()
		return nil, err
	}
	body := &httpTrackedBody{ReadCloser: response.Body, done: done}
	response.Body = body
	c.mu.Lock()
	if c.finished {
		c.mu.Unlock()
		_ = body.Close()
	} else {
		c.resources = append(c.resources, body)
		c.mu.Unlock()
	}
	return response, nil
}
func (c *HTTPCase) finish() error {
	c.mu.Lock()
	if c.finished {
		c.mu.Unlock()
		<-c.done
		return c.finishErr
	}
	c.finished = true
	resources := append([]io.Closer(nil), c.resources...)
	c.mu.Unlock()
	defer close(c.done)
	c.cancel()
	var failures []error
	for i := len(resources) - 1; i >= 0; i-- {
		if err := httpCleanupCall(resources[i].Close); err != nil {
			failures = append(failures, err)
		}
	}
	joined := make(chan struct{})
	go func() { c.work.Wait(); close(joined) }()
	timer := time.NewTimer(c.owner.config.CleanupTimeout)
	defer timer.Stop()
	select {
	case <-joined:
	case <-timer.C:
		failures = append(failures, errors.New("case HTTP work not joined; cleanup unconfirmed"))
	}
	c.finishErr = errors.Join(failures...)
	f := c.owner
	f.mu.Lock()
	defer f.mu.Unlock()
	f.active = false
	if c.finishErr != nil {
		f.failed = true
	}
	return c.finishErr
}

// Case acquires before hooks and releases only at this test's Cleanup, including
// Fatal/Goexit or parallel suspension. Call on the owning test goroutine.
func (f *HTTPFixture) Case(t *testing.T) *HTTPCase {
	t.Helper()
	c, err := f.reserve()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := c.finish(); err != nil {
			t.Error(httpFailure("case_cleanup", err))
		}
	})
	if err = c.setup(t.Context()); err != nil {
		t.Fatal(err)
	}
	return c
}
func (f *HTTPFixture) close() error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.closed {
		return f.closeErr
	}
	if f.active {
		f.failed = true
		return httpFailure("close", errors.New("active case not finished; cleanup unconfirmed"))
	}
	f.closed = true
	ctx, cancel := context.WithTimeout(context.Background(), f.config.CleanupTimeout)
	defer cancel()
	var failures []error
	for i := len(f.apps) - 1; i >= 0; i-- {
		if err := httpCleanupCall(func() error { return f.apps[i].StopReap(ctx) }); err != nil {
			failures = append(failures, err)
		}
	}
	if err := ctx.Err(); err != nil {
		failures = append(failures, err)
	}
	for _, resource := range []io.Closer{f.owners.live, f.owners.baseline, f.owners.source} {
		if resource != nil {
			if err := httpCleanupCall(resource.Close); err != nil {
				failures = append(failures, err)
			}
		}
	}
	if len(failures) > 0 {
		f.closeErr = httpFailure("owner_cleanup", errors.Join(failures...))
	}
	return f.closeErr
}
