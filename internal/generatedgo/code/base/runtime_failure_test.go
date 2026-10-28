package base

import (
	"errors"
	"runtime"
	"testing"
	"time"
)

func TestWorkerFailureNotifiesBeforeJoinAndCancelsWaits(t *testing.T) {
	m := allocationModule()
	m.Threads = &ThreadPool{}
	want := errors.New("controlled worker trap")
	notified := make(chan any, 4)
	m.Threads.NotifyWorkerFailure(func(cause any) { notified <- cause })
	// Both indefinite and timed waits must exit, even without a guest wake.
	for _, timeout := range []int64{-1, int64(time.Minute)} {
		ThreadLaunch(m, func(child *Module, _ int32) {
			AtomicWait32At(child, 64, 0, timeout)
			t.Error("failed instance resumed after wait")
		})
	}
	deadline := time.Now().Add(3 * time.Second)
	for {
		m.Threads.parkMu.Lock()
		n := len(m.Threads.parked[64])
		m.Threads.parkMu.Unlock()
		if n == 2 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("workers did not park")
		}
		runtime.Gosched()
	}
	// Pure Go work is not forcibly stopped and continues to own its memory.
	release := make(chan struct{})
	entered := make(chan struct{})
	ThreadLaunch(m, func(_ *Module, _ int32) { close(entered); <-release })
	<-entered
	ThreadLaunch(m, func(_ *Module, _ int32) { panic(want) })
	select {
	case got := <-notified:
		if got != want {
			t.Fatal(got)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("failure waited for quiescence")
	}
	joined := make(chan any, 1)
	go func() { joined <- m.Threads.WaitThreads() }()
	select {
	case got := <-joined:
		t.Fatalf("joined with a running owner: %v", got)
	default:
	}
	close(release)
	select {
	case got := <-joined:
		if got != want {
			t.Fatal(got)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("failed waits did not join")
	}
	if m.Threads.WaitThreads() != want {
		t.Fatal("join lost the original trap")
	}
	select {
	case got := <-notified:
		t.Fatalf("notification repeated: %v", got)
	default:
	}
	m.Threads.parkMu.Lock()
	defer m.Threads.parkMu.Unlock()
	if len(m.Threads.parked) != 0 {
		t.Fatal("failed waits retained parking entries")
	}
}
