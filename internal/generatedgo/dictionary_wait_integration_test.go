//go:build integration

package generatedgo

import (
	"bytes"
	"fmt"
	"io"
	"sync"
	"sync/atomic"
	"testing"
	"time"
	"unsafe"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p3"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p5"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p6"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p7"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p8"
)

// The source guard pins these actual guest bodies and their unchanged data.
const dictionaryLatch int32 = 18661504

type dictionaryWriter struct {
	base.Wasi_snapshot_preview1Imports
	once sync.Once
	run  func(*base.Module)
}

func (w *dictionaryWriter) Fd_write(m *base.Module, fd, iov, n, out int32) int32 {
	if fd == 1 {
		w.once.Do(func() { w.run(m) })
	}
	return w.Wasi_snapshot_preview1Imports.Fd_write(m, fd, iov, n, out)
}

type dictionaryWasix struct {
	base.Wasix_32v1Imports
	tap func(*base.Module, int32)
}

func (w *dictionaryWasix) Futex_wait(m *base.Module, a, b, c, d int32) int32 {
	w.tap(m, a)
	return w.Wasix_32v1Imports.Futex_wait(m, a, b, c, d)
}
func dictionaryWord(m *base.Module, a int32) *int32 {
	return (*int32)(unsafe.Add(m.M, base.MemoryEA(m, uint64(uint32(a)), 0, 4)))
}
func dictionaryRequire(ok bool, message string) {
	if !ok {
		panic("dictionary control: " + message)
	}
}
func dictionaryWait(ch <-chan struct{}, message string) {
	select {
	case <-ch:
	case <-time.After(2 * time.Second):
		panic("dictionary control timeout: " + message)
	}
}
func dictionaryFlags(m *base.Module) int32 {
	worker := *dictionaryWord(m, m.G1+396)
	if worker == 0 {
		return 0
	}
	return *dictionaryWord(m, worker+64)
}
func dictionaryLock(m *base.Module) {
	if base.AtomicRmwCmpxchg32(m, dictionaryLatch, 0, 0, 2147483647) != 0 {
		p6.Fn17730(m)
	}
	dictionaryRequire(m.ExcPending == 0, "owner lock exception")
}

// Same exclusive CAS/wake as the guest. Only the harness owner uses this;
// Fn17741 retains its own original lock and unlock implementation.
func dictionaryUnlock(m *base.Module) {
	for {
		waiters := atomic.LoadInt32(dictionaryWord(m, dictionaryLatch+4))
		state := atomic.LoadInt32(dictionaryWord(m, dictionaryLatch))
		dictionaryRequire(state&2147483647 == 2147483647, "exclusive owner state")
		if atomic.CompareAndSwapInt32(dictionaryWord(m, dictionaryLatch), state, 0) {
			if waiters != 0 || state < 0 {
				p8.Fn89(m, dictionaryLatch, 2147483647)
			}
			return
		}
	}
}

func TestDictionaryWaitActualGuest(t *testing.T) {
	warmProcessImage(t)
	for _, concurrency := range []int{1, 16} {
		for _, mode := range []string{"pending", "late-submit", "uncontended", "nonpool"} {
			if mode == "nonpool" && concurrency != 1 {
				continue
			}
			for repeat := 0; repeat < 3; repeat++ {
				t.Run(fmt.Sprintf("%s/P%d/%d", mode, concurrency, repeat), func(t *testing.T) {
					before := base.MemoryMappingStats()["active_mappings"]
					var tls, poolAddress, futexes atomic.Int32
					parked := make(chan struct{})
					var parkedOnce sync.Once
					var runErr any
					ran := false
					run := func(m *base.Module) {
						ran = true
						defer func() { runErr = recover() }()
						// Suppress only this controlled pool's periodic rescue timer via
						// its existing virtual start method. No notification is injected.
						m.T0 = append([]any(nil), m.T0...)
						timerIndex := *dictionaryWord(m, 16855320)
						dictionaryRequire(timerIndex == 12329, "timer virtual method binding")
						originalTimer := m.T0[timerIndex]
						starts := 0
						m.T0[timerIndex] = func(c *base.Module, timer, delay, period int32) {
							dictionaryRequire(delay == 0 && period > 0, "maintenance timer arguments")
							starts++
							poolAddress.Store(*dictionaryWord(c, timer+164))
						}
						pool := p3.Fn16607(m)
						m.T0[timerIndex] = originalTimer
						dictionaryRequire(pool != 0 && m.ExcPending == 0 && starts == 1 && poolAddress.Load() == pool, "controlled pool constructor")
						p8.Fn16601(m, pool, int32(concurrency))
						dictionaryRequire(*dictionaryWord(m, pool+344) == int32(concurrency), "effective concurrency")
						p5.Fn16600(m, pool) // Prime empty maintenance timestamp before queuing.
						initEntered, initRelease := make(chan struct{}), make(chan struct{})
						aDone, bDone, bRelease := make(chan struct{}), make(chan struct{}), make(chan struct{})
						ownerRelease := make(chan struct{})
						var initOnce, bOnce, ownerOnce sync.Once
						ownerHeld := false
						// On a failed progress assertion, release every fixture barrier
						// before joining the real workers; failures must not strand them.
						defer func() {
							initOnce.Do(func() { close(initRelease) })
							bOnce.Do(func() { close(bRelease) })
							ownerOnce.Do(func() { close(ownerRelease) })
							if ownerHeld {
								dictionaryUnlock(m)
							}
							if pool != 0 {
								p8.Fn16606(m, pool)
							}
						}()
						var created, retired, refs atomic.Int32
						add := func(f any) int32 { i := int32(len(m.T0)); m.T0 = append(m.T0, f); return i }
						allocate := func(size int32) int32 {
							p := p8.Fn157(m, 16, size)
							dictionaryRequire(p != 0 && p%16 == 0, "allocation")
							base.MemoryFill(m, p, 0, size)
							return p
						}
						table, taskA, taskB := allocate(12), allocate(16), allocate(16)
						originalInit := m.T0[*dictionaryWord(m, pool+12)].(func(*base.Module))
						originalDestroy := m.T0[*dictionaryWord(m, pool+16)].(func(*base.Module))
						*dictionaryWord(m, pool+12) = add(func(c *base.Module) {
							originalInit(c)
							if created.Add(1) == 1 && mode != "nonpool" {
								close(initEntered)
								dictionaryWait(initRelease, "initial worker release")
							}
						})
						*dictionaryWord(m, pool+16) = add(func(c *base.Module) { originalDestroy(c); retired.Add(1) })
						*dictionaryWord(m, table) = add(func(*base.Module, int32) { refs.Add(1) })
						*dictionaryWord(m, table+4) = add(func(*base.Module, int32) { refs.Add(-1) })
						*dictionaryWord(m, table+8) = add(p6.Fn16583)
						*dictionaryWord(m, taskA) = table
						*dictionaryWord(m, taskB) = table
						waiting := func(c *base.Module) int32 {
							p8.Fn16556(c, pool+184)
							n := *dictionaryWord(c, pool+372)
							p8.Fn16558(c, pool+184)
							return n
						}
						dictionaryRequire(*dictionaryWord(m, 18661580) < *dictionaryWord(m, 27743768), "dictionary below eviction threshold")
						evict := func(c *base.Module) {
							tls.Store(c.G1)
							dictionaryRequire(dictionaryFlags(c)&6 == 0, "caller is neither WAITING nor LONG")
							n := p6.Fn17741(c, 0) // Actual patched C guest; no begin/end supplied here.
							dictionaryRequire(c.ExcPending == 0 && n == 0, "normal eviction without dictionary mutation")
							dictionaryRequire(dictionaryFlags(c)&6 == 0, "WAITING/LONG restored by guest")
						}
						if mode == "nonpool" {
							ownerReady := make(chan struct{})
							*dictionaryWord(m, taskA+4) = add(func(c *base.Module, _ int32) {
								dictionaryLock(c)
								close(ownerReady)
								dictionaryWait(ownerRelease, "nonpool owner release")
								dictionaryUnlock(c)
								close(aDone)
							})
							p7.Fn16602(m, pool, taskA)
							dictionaryWait(ownerReady, "nonpool owner ready")
							dictionaryRequire(*dictionaryWord(m, m.G1+392) == 0 && *dictionaryWord(m, m.G1+396) == 0, "nonpool TLS")
							helperDone := make(chan struct{})
							go func() {
								defer close(helperDone)
								dictionaryWait(parked, "nonpool real futex")
								ownerOnce.Do(func() { close(ownerRelease) })
							}()
							evict(m)
							dictionaryWait(helperDone, "helper completion")
							dictionaryWait(aDone, "owner completion")
							dictionaryRequire(waiting(m) == 0, "nonpool notification is a no-op")
						} else {
							if mode != "uncontended" {
								dictionaryLock(m)
								ownerHeld = true
							}
							*dictionaryWord(m, taskA+4) = add(func(c *base.Module, _ int32) { evict(c); close(aDone) })
							*dictionaryWord(m, taskB+4) = add(func(*base.Module, int32) { close(bDone); dictionaryWait(bRelease, "queued task release") })
							p7.Fn16602(m, pool, taskA)
							dictionaryWait(initEntered, "initial worker")
							if mode != "late-submit" {
								p7.Fn16602(m, pool, taskB)
							}
							initOnce.Do(func() { close(initRelease) })
							if mode != "uncontended" {
								dictionaryWait(parked, "actual dictionary futex")
							}
							if mode == "late-submit" {
								p7.Fn16602(m, pool, taskB)
							}
							dictionaryWait(bDone, "queued progress without timer or owner release")
							expected := int32(1)
							if mode == "uncontended" {
								expected = 0
							}
							dictionaryRequire(waiting(m) == expected, "WAITING accounting during contention")
							if ownerHeld {
								select {
								case <-aDone:
									panic("dictionary control: eviction escaped exclusive owner")
								default:
								}
								dictionaryUnlock(m)
								ownerHeld = false
							}
							dictionaryWait(aDone, "eviction completion")
							dictionaryRequire(waiting(m) == 0, "WAITING accounting balanced after acquisition")
							bOnce.Do(func() { close(bRelease) })
						}
						// Join before checking retirement, refs, or releasing task storage.
						p8.Fn16606(m, pool)
						// Prevent the deferred failure cleanup from disposing twice.
						pool = 0
						expectedWorkers := int32(2)
						if mode == "uncontended" || mode == "nonpool" {
							expectedWorkers = 1
						}
						dictionaryRequire(created.Load() == expectedWorkers && retired.Load() == expectedWorkers && refs.Load() == 0, "worker and reference disposal")
						if mode == "uncontended" {
							dictionaryRequire(futexes.Load() == 0, "uncontended bypass")
						} else {
							dictionaryRequire(futexes.Load() > 0, "actual contended futex")
						}
						for _, p := range []int32{taskA, taskB, table} {
							p3.Fn153(m, p)
						}
					}
					tap := func(c *base.Module, address int32) {
						if address == dictionaryLatch && c.G1 == tls.Load() {
							futexes.Add(1)
							if mode != "nonpool" {
								dictionaryRequire(dictionaryFlags(c)&4 != 0, "guest marks worker WAITING before futex")
							}
							parkedOnce.Do(func() { close(parked) })
						}
					}
					var stderr bytes.Buffer
					done := startInstance(bytes.NewReader([]byte{0, 0, 0, 0}), io.Discard, &stderr, "", nil, false, nil, func(h *host) (*base.Module, func() error, error) {
						m, release, err := newMemoryModule(h)
						if err == nil {
							m.Wasi_snapshot_preview1 = &dictionaryWriter{Wasi_snapshot_preview1Imports: m.Wasi_snapshot_preview1, run: run}
							m.Wasix_32v1 = &dictionaryWasix{Wasix_32v1Imports: m.Wasix_32v1, tap: tap}
						}
						return m, release, err
					})
					select {
					case err := <-done:
						if err != nil {
							t.Fatalf("%v stderr=%s", err, stderr.String())
						}
					case <-time.After(10 * time.Second):
						t.Fatal("guest cleanup timeout")
					}
					if runErr != nil {
						t.Fatal(runErr)
					}
					if !ran {
						t.Fatal("ready interception absent")
					}
					if base.MemoryMappingStats()["active_mappings"] != before {
						t.Fatal("mapping debt")
					}
				})
			}
		}
	}
}
