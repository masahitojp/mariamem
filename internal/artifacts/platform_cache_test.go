package artifacts

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// All injected tests own their checker. The production singleton is exercised
// only in a disposable subprocess, never reset or mutated across test cases.
func testContext(t *testing.T) context.Context {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	t.Cleanup(cancel)
	return ctx
}

// Signal that a caller reached select on its context, without timing sleeps.
type waitingContext struct {
	context.Context
	waiting chan struct{}
	once    sync.Once
}

func (c *waitingContext) Done() <-chan struct{} {
	c.once.Do(func() { close(c.waiting) })
	return c.Context.Done()
}

func TestMacOSMajor(t *testing.T) {
	for _, output := range []string{"15.0", "27.0.1\n", " 16.2 \n"} {
		if _, err := macOSMajor(output); err != nil {
			t.Fatal(output, err)
		}
	}
	for _, output := range []string{"14.9", "", "garbage", "-1", "999999999999999999999999"} {
		if _, err := macOSMajor(output); err == nil {
			t.Fatal("accepted", output)
		}
	}
}

func TestPlatformCheckCanceledMiss(t *testing.T) {
	calls := 0
	c := platformCheck{probe: func(context.Context) error { calls++; return nil }}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := c.validate(ctx); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	if calls != 0 {
		t.Fatal(calls)
	}
}

func TestPlatformCheckSuccessAndCanceledHit(t *testing.T) {
	calls := 0
	c := platformCheck{probe: func(context.Context) error { calls++; return nil }}
	for i := 0; i < 8; i++ {
		if err := c.validate(testContext(t)); err != nil {
			t.Fatal(err)
		}
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := c.validate(ctx); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	if calls != 1 {
		t.Fatal(calls)
	}
}

func TestPlatformCheckFailureRecovery(t *testing.T) {
	for _, name := range []string{"command", "parse", "unsupported"} {
		t.Run(name, func(t *testing.T) {
			calls := 0
			failure := errors.New("command failed")
			if name == "parse" {
				_, failure = macOSMajor("invalid")
			}
			if name == "unsupported" {
				_, failure = macOSMajor("14.9")
			}
			c := platformCheck{probe: func(context.Context) error {
				calls++
				if calls == 1 {
					return failure
				}
				return nil
			}}
			if err := c.validate(testContext(t)); !errors.Is(err, failure) {
				t.Fatal(err)
			}
			if err := c.validate(testContext(t)); err != nil {
				t.Fatal(err)
			}
			if err := c.validate(testContext(t)); err != nil {
				t.Fatal(err)
			}
			if calls != 2 {
				t.Fatal(calls)
			}
		})
	}
}

func TestPlatformCheckConcurrentCohorts(t *testing.T) {
	for _, fail := range []bool{false, true} {
		t.Run(map[bool]string{false: "success", true: "failure"}[fail], func(t *testing.T) {
			const n = 32
			var calls, active, peak atomic.Int32
			start := make(chan struct{})
			failure := errors.New("unsupported or command failure")
			c := platformCheck{probe: func(context.Context) error {
				calls.Add(1)
				v := active.Add(1)
				for old := peak.Load(); v > old; old = peak.Load() {
					if peak.CompareAndSwap(old, v) {
						break
					}
				}
				defer active.Add(-1)
				if fail {
					return failure
				}
				return nil
			}}
			ctx := testContext(t)
			results := make(chan error, n)
			for i := 0; i < n; i++ {
				go func() { <-start; results <- c.validate(ctx) }()
			}
			close(start)
			for i := 0; i < n; i++ {
				err := <-results
				if fail && !errors.Is(err, failure) {
					t.Fatal(err)
				}
				if !fail && err != nil {
					t.Fatal(err)
				}
			}
			want := int32(1)
			if fail {
				want = n
			}
			if calls.Load() != want || peak.Load() != 1 {
				t.Fatalf("calls=%d want=%d peak=%d", calls.Load(), want, peak.Load())
			}
			if c.inFlight != nil {
				t.Fatal("unfinished probe")
			}
		})
	}
}

func TestPlatformCheckLeaderCancellation(t *testing.T) {
	started := make(chan struct{})
	var calls atomic.Int32
	c := platformCheck{probe: func(ctx context.Context) error {
		if calls.Add(1) == 1 {
			close(started)
			<-ctx.Done()
			return ctx.Err()
		}
		return nil
	}}
	leader, cancel := context.WithCancel(testContext(t))
	result := make(chan error, 1)
	go func() { result <- c.validate(leader) }()
	<-started
	waiter := make(chan error, 1)
	waitCtx := &waitingContext{Context: testContext(t), waiting: make(chan struct{})}
	go func() { waiter <- c.validate(waitCtx) }()
	<-waitCtx.waiting
	cancel()
	if err := <-result; !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	if err := <-waiter; err != nil {
		t.Fatal(err)
	}
	if calls.Load() != 2 {
		t.Fatal(calls.Load())
	}
}

func TestPlatformCheckWaiterCancellation(t *testing.T) {
	started, release := make(chan struct{}), make(chan struct{})
	var once sync.Once
	defer once.Do(func() { close(release) })
	c := platformCheck{probe: func(ctx context.Context) error {
		close(started)
		select {
		case <-release:
			return nil
		case <-ctx.Done():
			return ctx.Err()
		}
	}}
	ctx := testContext(t)
	result := make(chan error, 1)
	go func() { result <- c.validate(ctx) }()
	<-started
	waiter, cancel := context.WithCancel(ctx)
	waitCtx := &waitingContext{Context: waiter, waiting: make(chan struct{})}
	waitingResult := make(chan error, 1)
	go func() { waitingResult <- c.validate(waitCtx) }()
	<-waitCtx.waiting
	cancel()
	if err := <-waitingResult; !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	once.Do(func() { close(release) })
	if err := <-result; err != nil {
		t.Fatal(err)
	}
	if err := c.validate(ctx); err != nil {
		t.Fatal(err)
	}
}

func TestPlatformCheckCancellationAfterProbe(t *testing.T) {
	ctx, cancel := context.WithCancel(testContext(t))
	calls := 0
	c := platformCheck{probe: func(context.Context) error { calls++; cancel(); return nil }}
	if err := c.validate(ctx); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	c.probe = func(context.Context) error { calls++; return nil }
	if err := c.validate(testContext(t)); err != nil {
		t.Fatal(err)
	}
	if calls != 2 {
		t.Fatal("canceled result was cached", calls)
	}
}

func TestPlatformCheckCanceledCommandRetainsBothCauses(t *testing.T) {
	ctx, cancel := context.WithCancel(testContext(t))
	failure := errors.New("signal: killed")
	c := platformCheck{probe: func(context.Context) error { cancel(); return failure }}
	err := c.validate(ctx)
	if !errors.Is(err, context.Canceled) || !errors.Is(err, failure) {
		t.Fatal(err)
	}
	if c.ready || c.inFlight != nil {
		t.Fatal("canceled probe retained state")
	}
}

func TestPlatformCheckPanicReleasesWaiters(t *testing.T) {
	started, release := make(chan struct{}), make(chan struct{})
	var calls atomic.Int32
	c := platformCheck{probe: func(context.Context) error {
		if calls.Add(1) == 1 {
			close(started)
			<-release
			panic("probe panic")
		}
		return nil
	}}
	recovered := make(chan any, 1)
	ctx := testContext(t)
	go func() { defer func() { recovered <- recover() }(); _ = c.validate(ctx) }()
	<-started
	waiter := make(chan error, 1)
	waitCtx := &waitingContext{Context: ctx, waiting: make(chan struct{})}
	go func() { waiter <- c.validate(waitCtx) }()
	<-waitCtx.waiting
	close(release)
	if value := <-recovered; value != "probe panic" {
		t.Fatal(value)
	}
	if err := <-waiter; err != nil {
		t.Fatal(err)
	}
	if calls.Load() != 2 {
		t.Fatal(calls.Load())
	}
}

func TestMacOSProductionCheckSubprocess(t *testing.T) {
	if runtime.GOOS != "darwin" || runtime.GOARCH != "arm64" {
		t.Skip("native macOS arm64 path")
	}
	if os.Getenv("MARIAMEM_PLATFORM_CHECK_CHILD") == "1" {
		for i := 0; i < 2; i++ {
			if err := ValidatePlatform(testContext(t)); err != nil {
				t.Fatal(err)
			}
		}
		macOSPlatform.mu.Lock()
		ready := macOSPlatform.ready
		macOSPlatform.mu.Unlock()
		if !ready {
			t.Fatal("production Darwin path did not populate success cache")
		}
		return
	}
	command := exec.CommandContext(testContext(t), os.Args[0], "-test.run=^TestMacOSProductionCheckSubprocess$")
	command.Env = append(os.Environ(), "MARIAMEM_PLATFORM_CHECK_CHILD=1")
	if output, err := command.CombinedOutput(); err != nil {
		t.Fatalf("%v: %s", err, output)
	}
}
