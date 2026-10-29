package probe

import (
	"errors"
	"fmt"
	"os"
	"sync"
	"testing"
)

type owner struct {
	mu               sync.Mutex
	active, debt     bool
	resets, released int
}

func (o *owner) acquire(t *testing.T) bool {
	o.mu.Lock()
	defer o.mu.Unlock()
	if o.active || o.debt {
		return false
	}
	o.active = true
	o.resets++
	t.Cleanup(func() { o.mu.Lock(); defer o.mu.Unlock(); o.active = false; o.released++ })
	return true
}
func (o *owner) earlyRelease() { o.mu.Lock(); defer o.mu.Unlock(); o.active = false }
func TestParallelLease(t *testing.T) {
	o := &owner{}
	t.Run("group", func(t *testing.T) {
		t.Run("held", func(t *testing.T) {
			if !o.acquire(t) {
				t.Fatal("initial acquisition")
			}
			t.Parallel()
			o.mu.Lock()
			defer o.mu.Unlock()
			if o.resets != 1 || !o.active {
				t.Error("active case reset or lease lost")
			}
		})
		if os.Getenv("PROBE_MUTATION") == "early-release" {
			o.earlyRelease()
		}
		t.Run("overlap", func(t *testing.T) {
			if o.acquire(t) {
				t.Error("overlap admitted before active case cleanup")
			}
		})
	})
	if o.active || o.released != 1 {
		t.Fatalf("cleanup: active=%v releases=%d", o.active, o.released)
	}
	t.Run("next", func(t *testing.T) {
		if !o.acquire(t) {
			t.Fatal("healthy next case rejected")
		}
	})
	if o.resets != 2 || o.released != 2 {
		t.Fatal("reuse counts")
	}
}
func TestFatalCleanup(t *testing.T) {
	o := &owner{}
	t.Run("expected-fatal", func(t *testing.T) {
		if !o.acquire(t) {
			t.Fatal("acquire")
		}
		t.Fatal("INTENTIONAL_BODY_FAILURE")
	})
	if o.active || o.released != 1 {
		t.Fatal("Goexit failed to release")
	}
	t.Run("next", func(t *testing.T) {
		if !o.acquire(t) {
			t.Fatal("next rejected")
		}
	})
	if o.released != 2 {
		t.Fatal("next cleanup")
	}
	fmt.Println("GOEXIT_CLEANUP_OK")
}
func TestDebtStopsNext(t *testing.T) {
	o := &owner{}
	t.Run("debt", func(t *testing.T) {
		if !o.acquire(t) {
			t.Fatal("acquire")
		}
		t.Cleanup(func() { o.mu.Lock(); o.debt = true; o.mu.Unlock() })
	})
	t.Run("blocked", func(t *testing.T) {
		if o.acquire(t) {
			t.Fatal("debt admitted")
		}
	})
	if o.resets != 1 {
		t.Fatal("reset after debt")
	}
}
func TestIndependentOwners(t *testing.T) {
	for i := 0; i < 2; i++ {
		t.Run(fmt.Sprint(i), func(t *testing.T) {
			t.Parallel()
			o := &owner{}
			if !o.acquire(t) {
				t.Fatal("acquire")
			}
		})
	}
}

type app struct {
	stops int
	fail  bool
}

func (a *app) stop() error {
	a.stops++
	if a.fail {
		return errors.New("stop failed")
	}
	return nil
}
func construct(late, failStop bool) (error, *app, []string) {
	a := &app{fail: failStop}
	var registered *app
	events := []string{}
	register := func(a *app) { registered = a; events = append(events, "register") }
	if !late {
		register(a)
	}
	original := errors.New("readiness failed")
	events = append(events, "readiness-error")
	var cleanup error
	if registered != nil {
		events = append(events, "stop")
		cleanup = registered.stop()
	}
	events = append(events, "live-close", "baseline-close")
	return errors.Join(original, cleanup), a, events
}
func TestPartialStart(t *testing.T) {
	err, a, events := construct(os.Getenv("PROBE_MUTATION") == "late-register", true)
	if a.stops != 1 {
		t.Fatal("partial handle not stopped")
	}
	if err == nil || err.Error() != "readiness failed\nstop failed" {
		t.Fatal("original/cleanup error lost")
	}
	if fmt.Sprint(events) != "[register readiness-error stop live-close baseline-close]" {
		t.Fatal(events)
	}
}
