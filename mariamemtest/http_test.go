package mariamemtest

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

type httpFakeResource struct {
	events *[]string
	name   string
	fail   error
	count  int
}

func (r *httpFakeResource) Close() error {
	r.count++
	*r.events = append(*r.events, r.name)
	return r.fail
}

type httpFakeLive struct {
	httpFakeResource
	gen       uint64
	failReset error
}

func (l *httpFakeLive) ConnectionInfo() mariamem.ConnectionInfo {
	return mariamem.ConnectionInfo{Host: "127.0.0.1", Port: 42}
}
func (l *httpFakeLive) Status() mariamem.LiveStatus {
	return mariamem.LiveStatus{State: "ready", Generation: l.gen}
}
func (l *httpFakeLive) Reset(ctx context.Context, _ mariamem.ResetOptions) error {
	*l.events = append(*l.events, "reset")
	if l.failReset != nil {
		return l.failReset
	}
	l.gen++
	return nil
}

type httpFakeApp struct {
	events                *[]string
	failStop, failQuiesce error
	url                   string
}

func (a *httpFakeApp) BaseURL() string  { return a.url }
func (a *httpFakeApp) Identity() string { return "app-1" }
func (a *httpFakeApp) QuiesceAndRetire(ctx context.Context) error {
	*a.events = append(*a.events, "quiesce")
	return a.failQuiesce
}
func (a *httpFakeApp) StopReap(ctx context.Context) error {
	*a.events = append(*a.events, "stop")
	return a.failStop
}
func httpHarness(t *testing.T) (*HTTPFixture, *httpFakeLive, *httpFakeApp, *[]string) {
	t.Helper()
	events := []string{}
	live := &httpFakeLive{httpFakeResource: httpFakeResource{events: &events, name: "live.close"}}
	app := &httpFakeApp{events: &events, url: "http://127.0.0.1:1234"}
	cfg := HTTPConfig{Prepare: func(context.Context, *mariamem.Database) error { return nil }, StartReady: func(ctx context.Context, target mariamem.ConnectionInfo, register func(HTTPApp) error) (HTTPApp, error) {
		if err := register(app); err != nil {
			return nil, err
		}
		events = append(events, "start")
		return app, nil
	}, SoleWorkSource: true}
	factory := func(ctx context.Context, c HTTPConfig, o *httpOwners) error {
		o.source = &httpFakeResource{events: &events, name: "source.close"}
		o.baseline = &httpFakeResource{events: &events, name: "baseline.close"}
		o.live = live
		events = append(events, "prepare")
		return nil
	}
	f, err := newHTTP(cfg, factory)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := f.close(); err != nil {
			t.Error(err)
		}
	})
	return f, live, app, &events
}
func TestHTTPCaseOrderAndLease(t *testing.T) {
	f, l, _, events := httpHarness(t)
	t.Run("first", func(t *testing.T) {
		c := f.Case(t)
		if c.Client == nil {
			t.Fatal("client")
		}
		if _, err := f.reserve(); err == nil {
			t.Fatal("overlap admitted")
		}
	})
	t.Run("next", func(t *testing.T) { f.Case(t) })
	if l.gen != 2 {
		t.Fatal("reset count", l.gen)
	}
	if fmt.Sprint((*events)[:4]) != "[prepare start quiesce reset]" {
		t.Fatal(*events)
	}
}
func TestHTTPParallelSuspension(t *testing.T) {
	f, l, _, _ := httpHarness(t)
	t.Run("group", func(t *testing.T) {
		t.Run("held", func(t *testing.T) {
			f.Case(t)
			t.Parallel()
			if l.gen != 1 {
				t.Fatal("reset underneath suspended case")
			}
		})
		t.Run("overlap", func(t *testing.T) {
			if _, err := f.reserve(); err == nil {
				t.Fatal("overlap admitted")
			}
		})
	})
	t.Run("next", func(t *testing.T) { f.Case(t) })
}
func TestHTTPFailureLatches(t *testing.T) {
	for _, stage := range []string{"quiesce", "reset", "resume", "external"} {
		t.Run(stage, func(t *testing.T) {
			f, l, a, _ := httpHarness(t)
			original := errors.New("failure")
			switch stage {
			case "quiesce":
				a.failQuiesce = original
			case "reset":
				l.failReset = original
			case "resume":
				f.config.Resume = func(context.Context, HTTPApp) error { return original }
			case "external":
				f.config.ExternalState = func(context.Context, HTTPApp, func(io.Closer) error) error { return original }
			}
			c, err := f.reserve()
			if err != nil {
				t.Fatal(err)
			}
			err = c.setup(context.Background())
			if !errors.Is(err, original) {
				t.Fatal("lost cause", err)
			}
			if err = c.finish(); err != nil {
				t.Fatal(err)
			}
			if _, err = f.reserve(); err == nil {
				t.Fatal("later admission")
			}
		})
	}
}
func TestHTTPCleanupDebt(t *testing.T) {
	f, _, _, events := httpHarness(t)
	c, err := f.reserve()
	if err != nil {
		t.Fatal(err)
	}
	failure := errors.New("cleanup")
	if err = c.Register(&httpFakeResource{events: events, name: "external", fail: failure}); err != nil {
		t.Fatal(err)
	}
	if !errors.Is(c.finish(), failure) {
		t.Fatal("cleanup cause lost")
	}
	if _, err = f.reserve(); err == nil {
		t.Fatal("debt admitted")
	}
}
func TestHTTPPartialStart(t *testing.T) {
	events := []string{}
	original := errors.New("readiness")
	stopErr := errors.New("stop")
	liveErr, baselineErr, sourceErr := errors.New("live close"), errors.New("baseline close"), errors.New("source close")
	app := &httpFakeApp{events: &events, url: "http://x", failStop: stopErr}
	cfg := HTTPConfig{Prepare: func(context.Context, *mariamem.Database) error { return nil }, SoleWorkSource: true, StartReady: func(ctx context.Context, target mariamem.ConnectionInfo, register func(HTTPApp) error) (HTTPApp, error) {
		if err := register(app); err != nil {
			t.Fatal(err)
		}
		return nil, original
	}}
	f, err := newHTTP(cfg, func(ctx context.Context, c HTTPConfig, o *httpOwners) error {
		o.live = &httpFakeLive{httpFakeResource: httpFakeResource{events: &events, name: "live.close", fail: liveErr}}
		o.baseline = &httpFakeResource{events: &events, name: "baseline.close", fail: baselineErr}
		o.source = &httpFakeResource{events: &events, name: "source.close", fail: sourceErr}
		return nil
	})
	for _, cause := range []error{original, stopErr, liveErr, baselineErr, sourceErr} {
		if !errors.Is(err, cause) {
			t.Fatal("lost original/cleanup", cause, err)
		}
	}
	if fmt.Sprint(events) != "[stop live.close baseline.close source.close]" {
		t.Fatal(events)
	}
	_ = f.close()
	if len(events) != 4 {
		t.Fatal("double cleanup")
	}
}

func TestHTTPPartialLiveCreationRetainsAllOwners(t *testing.T) {
	events := []string{}
	original := errors.New("live creation")
	liveErr, baselineErr, sourceErr := errors.New("live close"), errors.New("baseline close"), errors.New("source close")
	live := &httpFakeLive{httpFakeResource: httpFakeResource{events: &events, name: "live.close", fail: liveErr}}
	baseline := &httpFakeResource{events: &events, name: "baseline.close", fail: baselineErr}
	source := &httpFakeResource{events: &events, name: "source.close", fail: sourceErr}
	cfg := HTTPConfig{Prepare: func(context.Context, *mariamem.Database) error { return nil }, SoleWorkSource: true,
		StartReady: func(context.Context, mariamem.ConnectionInfo, func(HTTPApp) error) (HTTPApp, error) {
			t.Fatal("partial Live admitted application startup")
			return nil, nil
		}}
	f, err := newHTTP(cfg, func(_ context.Context, _ HTTPConfig, o *httpOwners) error {
		o.source, o.baseline, o.live = source, baseline, live
		return original
	})
	for _, cause := range []error{original, liveErr, baselineErr, sourceErr} {
		if !errors.Is(err, cause) {
			t.Fatal("lost cause", cause, err)
		}
	}
	if _, err := f.reserve(); err == nil {
		t.Fatal("partial Live admitted case")
	}
	_ = f.close()
	if fmt.Sprint(events) != "[live.close baseline.close source.close]" || live.count != 1 || baseline.count != 1 || source.count != 1 {
		t.Fatal("partial owner missing or cleaned twice", events)
	}
}

type httpCleanupContextApp struct {
	*httpFakeApp
	stopped bool
}

func (a *httpCleanupContextApp) StopReap(ctx context.Context) error {
	if ctx.Err() != nil {
		return fmt.Errorf("cleanup inherited canceled case: %w", ctx.Err())
	}
	if _, ok := ctx.Deadline(); !ok {
		return errors.New("cleanup has no deadline")
	}
	a.stopped = true
	return a.httpFakeApp.StopReap(ctx)
}

func TestHTTPCanceledCaseStillStopsApp(t *testing.T) {
	f, _, app, events := httpHarness(t)
	observed := &httpCleanupContextApp{httpFakeApp: app}
	f.app, f.apps = observed, []HTTPApp{observed}
	c, err := f.reserve()
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err = c.setup(ctx); !errors.Is(err, context.Canceled) {
		t.Fatal("original cancellation lost", err)
	}
	if err = c.finish(); err != nil {
		t.Fatal(err)
	}
	if err = f.close(); err != nil || !observed.stopped {
		t.Fatal("app cleanup not confirmed", err)
	}
	if fmt.Sprint((*events)[len(*events)-4:]) != "[stop live.close baseline.close source.close]" {
		t.Fatal(*events)
	}
}
func TestHTTPClientOwnedBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, "body") }))
	defer server.Close()
	f, _, _, _ := httpHarness(t)
	c, err := f.reserve()
	if err != nil {
		t.Fatal(err)
	}
	if err = c.setup(context.Background()); err != nil {
		t.Fatal(err)
	}
	response, err := c.Client.Get(server.URL)
	if err != nil {
		t.Fatal(err)
	}
	// Intentionally unclosed body is owned by the case, so finish joins it.
	if err = c.finish(); err != nil {
		t.Fatal(err)
	}
	_ = response.Body.Close()
	if _, err = c.Client.Get(server.URL); err == nil {
		t.Fatal("request after finish")
	}
}
func TestHTTPFatalChild(t *testing.T) {
	if os.Getenv("E2E_FATAL_CHILD") != "1" {
		return
	}
	f, _, _, _ := httpHarness(t)
	t.Run("intentional", func(t *testing.T) { f.Case(t); t.Fatal("INTENTIONAL_BODY_FAILURE") })
	t.Run("next", func(t *testing.T) { f.Case(t) })
	if f.active {
		t.Fatal("lease not released")
	}
	fmt.Println("FATAL_CLEANUP_AND_NEXT_OK")
}
func TestHTTPFatalCleanupSubprocess(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, os.Args[0], "-test.run=^TestHTTPFatalChild$", "-test.v")
	cmd.Env = append(os.Environ(), "E2E_FATAL_CHILD=1")
	output, err := cmd.CombinedOutput()
	if err == nil || ctx.Err() != nil {
		t.Fatalf("expected body failure: %v %s", err, output)
	}
	if !strings.Contains(string(output), "FATAL_CLEANUP_AND_NEXT_OK") || strings.Contains(string(output), "DATA RACE") {
		t.Fatal(string(output))
	}
}

func TestHTTPCleanupPanicContinues(t *testing.T) {
	f, _, _, events := httpHarness(t)
	c, err := f.reserve()
	if err != nil {
		t.Fatal(err)
	}
	if err = c.Register(httpCloseFunc(func() error { panic("cleanup panic") })); err != nil {
		t.Fatal(err)
	}
	if err = c.Register(&httpFakeResource{events: events, name: "other"}); err != nil {
		t.Fatal(err)
	}
	if err = c.finish(); err == nil {
		t.Fatal("panic lost")
	}
	if (*events)[len(*events)-1] != "other" {
		t.Fatal(*events)
	}
	if _, err = f.reserve(); err == nil {
		t.Fatal("debt admitted")
	}
}
func TestHTTPContextCancellation(t *testing.T) {
	f, l, _, _ := httpHarness(t)
	c, err := f.reserve()
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err = c.setup(ctx); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	_ = c.finish()
	if l.gen != 0 {
		t.Fatal("reset after canceled quiesce")
	}
}
func TestHTTPConfigurationBeforeAllocation(t *testing.T) {
	called := false
	_, err := newHTTP(HTTPConfig{}, func(context.Context, HTTPConfig, *httpOwners) error { called = true; return nil })
	if err == nil || called {
		t.Fatal("invalid config allocated owner")
	}
}
