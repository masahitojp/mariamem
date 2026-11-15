//go:build mappingspike && darwin && arm64

package base

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"runtime/debug"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"
)

func TestResetSpikeProtection(t *testing.T) {
	if os.Getenv("RESET_GUARD") == "1" {
		b, e := NewMemoryMapping(65536, 4*65536)
		if e != nil {
			t.Fatal(e)
		}
		defer b.Close()
		if e = replaceAnonymous(b.memory); e != nil {
			t.Fatal(e)
		}
		debug.SetPanicOnFault(true)
		defer func() {
			if recover() == nil {
				t.Error("PROT_NONE readable")
			} else {
				fmt.Println("EXPECTED_RESET_GUARD")
			}
		}()
		fmt.Println(b.memory[0])
		return
	}
	c := exec.Command(os.Args[0], "-test.run=^TestResetSpikeProtection$")
	c.Env = append(os.Environ(), "RESET_GUARD=1")
	out, e := c.CombinedOutput()
	if e != nil || !strings.Contains(string(out), "EXPECTED_RESET_GUARD") {
		t.Fatalf("guard: %v %s", e, out)
	}
}
func resetCPU() float64 {
	var r syscall.Rusage
	syscall.Getrusage(syscall.RUSAGE_SELF, &r)
	return float64(r.Utime.Sec+r.Stime.Sec)*1000 + float64(r.Utime.Usec+r.Stime.Usec)/1000
}
func TestResetSpikeCycle(t *testing.T) {
	dir := os.Getenv("RESET_FIXTURE")
	if dir == "" {
		t.Skip("finite runner only")
	}
	arm := os.Getenv("RESET_ARM")
	p, _ := strconv.Atoi(os.Getenv("RESET_P"))
	dirty, _ := strconv.Atoi(os.Getenv("RESET_DIRTY"))
	if (p != 1 && p != 2) || (dirty != 0 && dirty != 1 && dirty != 64) || (arm != "baseline" && arm != "reset") {
		t.Fatal("invalid campaign")
	}
	f, e := os.Open(dir + "/image")
	if e != nil {
		t.Fatal(e)
	}
	defer f.Close()
	raw, e := os.ReadFile(dir + "/ranges.json")
	if e != nil {
		t.Fatal(e)
	}
	var rs []ImageRange
	if e = json.Unmarshal(raw, &rs); e != nil {
		t.Fatal(e)
	}
	const initial = 256 << 20
	const maximum = 2 << 30
	const grown = 320 << 20
	before := MemoryMappingStats()
	start := time.Now()
	cpu := resetCPU()
	var wg sync.WaitGroup
	errs := make(chan error, p)
	for w := 0; w < p; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			var slot *resetSlot
			if arm == "reset" {
				b, e := NewMemoryMapping(0, maximum)
				if e != nil {
					errs <- e
					return
				}
				slot = &resetSlot{b: b, reset: replaceAnonymous}
				defer func() {
					if e := slot.close(); e != nil {
						errs <- e
					}
				}()
			}
			for n := 0; n < 48; n++ {
				var b *MemoryMapping
				var epoch uint64
				var e error
				if slot != nil {
					epoch, e = slot.acquire(initial, int(f.Fd()), rs)
					b = slot.b
				} else {
					b, e = NewStaticPageMapping(int(f.Fd()), initial, maximum, rs)
				}
				if e != nil {
					errs <- e
					return
				}
				if e = b.Grow(initial, grown); e != nil {
					errs <- e
					return
				}
				// Equal page-touch pattern: half in initial image/anonymous area, half grown.
				pages := dirty * (1 << 20) / os.Getpagesize()
				for i := 0; i < pages; i++ {
					off := 8<<20 + (i/2)*os.Getpagesize()
					if i%2 == 1 {
						off = initial + (i/2)*os.Getpagesize()
					}
					b.memory[off] = byte(n + 17)
				}
				if slot != nil {
					e = slot.release(epoch)
				} else {
					e = b.Close()
				}
				if e != nil {
					errs <- e
					return
				}
			}
		}()
	}
	wg.Wait()
	wall := float64(time.Since(start)) / 1e6
	cpu = resetCPU() - cpu
	close(errs)
	for e := range errs {
		t.Fatal(e)
	}
	after := MemoryMappingStats()
	for _, k := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes"} {
		if after[k] != before[k] {
			t.Fatal("resource residue", k)
		}
	}
	out, _ := json.Marshal(map[string]any{"arm": arm, "p": p, "dirty_mib": dirty, "cycles_per_worker": 48, "wall_ms": wall, "cpu_ms": cpu, "before": before, "after": after, "ranges": len(rs)})
	fmt.Println("RESET_RESULT " + string(out))
}
