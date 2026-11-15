package generatedgo

import (
	"context"
	"errors"
	"github.com/masahitojp/mariamem/internal/disposal"
	"io"
	"strings"
	"sync/atomic"
	"testing"
	"time"
	"unsafe"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

func trapTestModule() *base.Module {
	mem := make([]byte, 65536)
	size := &atomic.Uint64{}
	size.Store(uint64(len(mem)))
	return &base.Module{Memory: mem, M: unsafe.Pointer(&mem[0]), MemSize: size, MemShared: true, Threads: &base.ThreadPool{}}
}

func TestControlledGuestMemoryTraps(t *testing.T) {
	for _, worker := range []bool{false, true} {
		for _, family := range []string{"scalar", "simd", "atomic"} {
			for _, width := range []uint64{1, 2, 4, 8} {
				m := trapTestModule()
				body := func(m *base.Module, _ int32) {
					switch family {
					case "scalar":
						base.MemoryEA(m, 65536, 0, width)
					case "simd":
						base.Simd_v128_load(m, 65536, 0)
					case "atomic":
						base.AtomicRmwAdd32(m, 65536, 0, 1)
					}
				}
				err := executeGuest(m, func(m *base.Module) {
					if worker {
						base.ThreadLaunch(m, body)
					} else {
						body(m, 0)
					}
				})
				if err == nil || !strings.Contains(err.Error(), "out of bounds") {
					t.Fatalf("worker=%v family=%s width=%d: %v", worker, family, width, err)
				}
				if worker && m.Threads.WaitThreads() == nil {
					t.Fatal("a second join lost the worker failure")
				}
			}
		}
	}
	// A fresh instance remains usable in this same host after all guest traps.
	m := trapTestModule()
	if err := executeGuest(m, func(m *base.Module) {
		base.ThreadLaunch(m, func(child *base.Module, _ int32) {
			atomic.StoreUint32(base.AtomicPtr32At(child, base.AtomicEA(child, 64, 0, 4)), 42)
		})
	}); err != nil || atomic.LoadUint32(base.AtomicPtr32At(m, 64)) != 42 {
		t.Fatal("host/fresh-instance survival", err)
	}
}

func TestControlledGuestJoinBeforeCleanup(t *testing.T) {
	for _, rootTrap := range []bool{false, true} {
		m := trapTestModule()
		entered, release, exited := make(chan struct{}), make(chan struct{}), make(chan struct{})
		done := make(chan error, 1)
		go func() {
			done <- executeGuest(m, func(m *base.Module) {
				base.ThreadLaunch(m, func(_ *base.Module, _ int32) {
					close(entered)
					<-release
					close(exited)
					panic(errors.New("worker trap"))
				})
				<-entered
				if rootTrap {
					panic("root trap")
				}
			})
		}()
		<-entered
		select {
		case err := <-done:
			t.Fatalf("completion before worker exit: %v", err)
		case <-time.After(10 * time.Millisecond):
		}
		close(release)
		select {
		case err := <-done:
			if err == nil || !strings.Contains(err.Error(), "worker trap") || (rootTrap && !strings.Contains(err.Error(), "root trap")) {
				t.Fatal("lost root/worker failure", err)
			}
			select {
			case <-exited:
			default:
				t.Fatal("worker not joined")
			}
		case <-time.After(time.Second):
			t.Fatal("cooperative join did not complete")
		}
	}
}

func TestControlledGuestPartialInitialization(t *testing.T) {
	if err := executeGuest(nil, func(_ *base.Module) { panic("initialization trap") }); err == nil || !strings.Contains(err.Error(), "initialization trap") {
		t.Fatal(err)
	}
}

func TestControlledGuestFailedWorkerWithRunningPeer(t *testing.T) {
	m := trapTestModule()
	peerEntered, releasePeer := make(chan struct{}), make(chan struct{})
	rootReturned := make(chan struct{})
	done := make(chan error, 1)
	go func() {
		done <- executeGuest(m, func(m *base.Module) {
			base.ThreadLaunch(m, func(child *base.Module, _ int32) {
				<-peerEntered
				base.MemoryEA(child, 65536, 0, 1)
			})
			base.ThreadLaunch(m, func(_ *base.Module, _ int32) {
				close(peerEntered)
				<-releasePeer
			})
			close(rootReturned)
		})
	}()
	<-rootReturned
	<-peerEntered
	select {
	case err := <-done:
		t.Fatalf("returned while a peer still owns memory: %v", err)
	case <-time.After(10 * time.Millisecond):
	}
	close(releasePeer)
	select {
	case err := <-done:
		if err == nil || !strings.Contains(err.Error(), "out of bounds") {
			t.Fatal(err)
		}
	case <-time.After(time.Second):
		t.Fatal("cooperative peer release did not complete")
	}
}

func TestControlledGuestFirstWorkerTrap(t *testing.T) {
	m := trapTestModule()
	base.ThreadLaunch(m, func(_ *base.Module, _ int32) { panic("first worker trap") })
	first := m.Threads.WaitThreads()
	if first != "first worker trap" {
		t.Fatal(first)
	}
	// Later failure and simultaneous readers must retain the first failure.
	base.ThreadLaunch(m, func(_ *base.Module, _ int32) { panic("later worker trap") })
	if got := m.Threads.WaitThreads(); got != first {
		t.Fatal(got)
	}
	done := make(chan any, 8)
	for i := 0; i < cap(done); i++ {
		go func() { done <- m.Threads.WaitThreads() }()
	}
	for i := 0; i < cap(done); i++ {
		if got := <-done; got != first {
			t.Fatal(got)
		}
	}
}

func TestGuestEnvironmentIsPerInstance(t *testing.T) {
	t.Setenv("MARIAMEM_UCA_VERIFY_INTERNAL", "1")
	t.Setenv("MARIAMEM_BOOT_MODE", "restore")
	t.Setenv("MARIAMEM_GUEST_TIMING", "1")
	for _, restore := range []bool{false, true} {
		for _, timing := range []bool{false, true} {
			want := []string{"MARIAMEM_BOOT_MODE=fresh"}
			if restore {
				want[0] = "MARIAMEM_BOOT_MODE=restore"
			}
			if timing {
				want = append(want, "MARIAMEM_GUEST_TIMING=1")
			}
			got := guestEnvironment(restore, timing)
			if strings.Join(got, "\n") != strings.Join(want, "\n") {
				t.Fatalf("restore=%v timing=%v: %v", restore, timing, got)
			}
			got[0] = "modified"
			if guestEnvironment(restore, timing)[0] != want[0] {
				t.Fatal("guest context aliases another instance")
			}
		}
	}
}

func TestReleaseFailureRetainsOwner(t *testing.T) {
	var allowed atomic.Bool
	failure := errors.New("release refused")
	err := retainRelease(func() error {
		if !allowed.Load() {
			return failure
		}
		return nil
	})
	owners := disposal.Owners(err)
	if len(owners) != 1 || owners[0].Complete() {
		t.Fatal("lost ownership", err)
	}
	allowed.Store(true)
	if e := disposal.Retry(context.Background(), err); e != nil {
		t.Fatal(e)
	}
	if !owners[0].Complete() || !errors.Is(err, failure) {
		t.Fatal("wrong completion/result", err)
	}
}

func TestStoppedWaitsForWorkersBeforeGatedRelease(t *testing.T) {
	workerStarted := make(chan struct{})
	workerRelease := make(chan struct{})
	releaseEntered := make(chan struct{})
	releaseGate := make(chan struct{})
	stopped := make(chan error, 1)
	failure := errors.New("root trapped")
	done := runInstance(nil, io.Discard, io.Discard, "", nil, false, nil,
		func(*host) (*base.Module, func() error, error) {
			return trapTestModule(), func() error { close(releaseEntered); <-releaseGate; return nil }, nil
		},
		func(err error) { stopped <- err }, func(m *base.Module) {
			base.ThreadLaunch(m, func(*base.Module, int32) { close(workerStarted); <-workerRelease })
			<-workerStarted
			panic(failure)
		})
	<-workerStarted
	select {
	case <-stopped:
		t.Fatal("stopped before worker join")
	case <-time.After(20 * time.Millisecond):
	}
	close(workerRelease)
	select {
	case err := <-stopped:
		if !errors.Is(err, failure) {
			t.Fatal(err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("missing stop")
	}
	<-releaseEntered
	select {
	case <-done:
		t.Fatal("completed before release")
	default:
	}
	close(releaseGate)
	if err := <-done; !errors.Is(err, failure) {
		t.Fatal(err)
	}
}

func TestStoppedReportsConstructionFailure(t *testing.T) {
	failure := errors.New("construction failed")
	stopped := make(chan error, 1)
	done := startInstanceWithStopped(nil, io.Discard, io.Discard, "", nil, false, nil,
		func(*host) (*base.Module, func() error, error) { return nil, nil, failure }, func(err error) { stopped <- err })
	select {
	case err := <-stopped:
		if !errors.Is(err, failure) {
			t.Fatal(err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("missing stop on construction failure")
	}
	if err := <-done; !errors.Is(err, failure) {
		t.Fatal(err)
	}
}
