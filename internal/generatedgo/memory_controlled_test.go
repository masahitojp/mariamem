//go:build (darwin && arm64) || (linux && amd64)

package generatedgo

import (
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p8"
)

func TestMappedControlledTrapsRelease(t *testing.T) {
	before := base.MemoryMappingStats()
	for _, worker := range []bool{false, true} {
		for _, family := range []string{"scalar", "simd", "atomic", "unaligned", "offset-overflow"} {
			m, release, err := newMemoryModule(mappedTestHost())
			if err != nil {
				t.Fatal(err)
			}
			body := func(child *base.Module, _ int32) {
				end := int32(child.MemSize.Load())
				switch family {
				case "scalar":
					child.G1 = end - 4
					p8.Fn68(child)
				case "simd":
					base.Simd_v128_load(child, end-15, 0)
				case "atomic":
					base.AtomicRmwAdd64(child, end, 0, 1)
				case "unaligned":
					base.AtomicRmwAdd32(child, 3, 0, 1)
				case "offset-overflow":
					base.MemoryEA(child, 1, 0xffffffff, 4)
				}
			}
			err = func() (err error) {
				defer releaseMemoryModule(m, release, &err)
				return executeGuest(m, func(m *base.Module) {
					if worker {
						base.ThreadLaunch(m, body)
					} else {
						body(m, 0)
					}
				})
			}()
			if err == nil || !strings.Contains(err.Error(), "wasm:") {
				t.Fatal(worker, family, err)
			}
			if err = release(); err != nil {
				t.Fatal("repeated release", err)
			}
		}
	}
	after := base.MemoryMappingStats()
	if after["active_mappings"] != before["active_mappings"] || after["releases"]-before["releases"] != 10 || after["creates"]-before["creates"] != 10 {
		t.Fatal("controlled failure ownership", before, after)
	}
	// The same Go host can create and dispose a valid new instance after traps.
	m, release, err := newMemoryModule(mappedTestHost())
	if err != nil {
		t.Fatal(err)
	}
	err = func() (err error) {
		defer releaseMemoryModule(m, release, &err)
		return executeGuest(m, func(m *base.Module) { base.MemoryEA(m, 64, 0, 8) })
	}()
	if err != nil {
		t.Fatal(err)
	}
}

func TestMappedFailureErrorOwnershipPreserved(t *testing.T) {
	want := errors.New("owned cleanup failure")
	if got := executeGuest(nil, func(*base.Module) { panic(want) }); !errors.Is(got, want) {
		t.Fatal("recover lost cleanup ownership", got)
	}
}

func TestMappedControlledWorkerTrapWaitsForPeer(t *testing.T) {
	before := base.MemoryMappingStats()
	m, release, err := newMemoryModule(mappedTestHost())
	if err != nil {
		t.Fatal(err)
	}
	entered, unblock, rootReturned := make(chan struct{}), make(chan struct{}), make(chan struct{})
	done := make(chan error, 1)
	go func() {
		var err error
		defer func() { done <- err }()
		defer releaseMemoryModule(m, release, &err)
		err = executeGuest(m, func(m *base.Module) {
			base.ThreadLaunch(m, func(child *base.Module, _ int32) {
				<-entered
				base.AtomicRmwAdd32(child, int32(child.MemSize.Load()), 0, 1)
			})
			base.ThreadLaunch(m, func(child *base.Module, _ int32) {
				close(entered)
				<-unblock
				child.Memory[64] = 7
			})
			close(rootReturned)
		})
	}()
	<-rootReturned
	<-entered
	select {
	case err := <-done:
		t.Fatalf("unmapped with live peer: %v", err)
	case <-time.After(10 * time.Millisecond):
	}
	if base.MemoryMappingStats()["active_mappings"] != before["active_mappings"]+1 {
		t.Fatal("premature unmap")
	}
	close(unblock)
	select {
	case err := <-done:
		if err == nil || !strings.Contains(err.Error(), "wasm:") {
			t.Fatal(err)
		}
	case <-time.After(time.Second):
		t.Fatal("cooperative join did not finish")
	}
	if err := release(); err != nil {
		t.Fatal(err)
	}
	after := base.MemoryMappingStats()
	if after["active_mappings"] != before["active_mappings"] || after["releases"] != before["releases"]+1 {
		t.Fatal(before, after)
	}
}
