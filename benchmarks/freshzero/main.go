package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/freshzero/common"
	"github.com/masahitojp/mariamem/internal/generatedgo"
	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"runtime"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"
)

type Child struct {
	WallMS float64 `json:"wall_ms"`
	CPUMS  float64 `json:"cpu_ms"`
}
type Result struct {
	Stages   []Stage           `json:"stages"`
	Observed bool              `json:"observed"`
	Success  bool              `json:"success"`
	Error    string            `json:"error,omitempty"`
	Cleanup  bool              `json:"cleanup"`
	Children []Child           `json:"children"`
	Final    map[string]uint64 `json:"final"`
}

var input = bufio.NewReader(os.Stdin)

func checkpoint(name string) {
	b, _ := json.Marshal(map[string]any{"checkpoint": name})
	fmt.Println(string(b))
	if _, e := input.ReadString('\n'); e != nil {
		panic(e)
	}
}
func cpu() float64 {
	var r syscall.Rusage
	if e := syscall.Getrusage(syscall.RUSAGE_SELF, &r); e != nil {
		panic(e)
	}
	return float64(r.Utime.Sec+r.Stime.Sec)*1000 + float64(r.Utime.Usec+r.Stime.Usec)/1000
}
func run(corrupt, observed bool) (result Result, err error) {
	result.Observed = observed
	var enabled bool
	var child int
	var current []byte
	var size *atomic.Uint64
	if observed {
		generatedgo.FreshZeroHook = func(stage string, b []byte, s *atomic.Uint64, wall, cpu float64) {
			current = b
			size = s
			if enabled {
				result.Stages = append(result.Stages, stageRecord(fmt.Sprintf("child%d_%s", child, stage), b, wall, cpu))
			}
		}
	}
	ctx, cancel := common.Context()
	defer cancel()
	var children []*mariamem.Database
	sn, e := common.Prepare(ctx)
	if e != nil {
		return result, e
	}
	defer func() {
		for _, d := range children {
			err = errors.Join(err, d.Close())
		}
		err = errors.Join(err, sn.Close())
		result.Final = base.MemoryMappingStats()
		result.Cleanup = result.Final["active_mappings"] == 0
		result.Success = err == nil && result.Cleanup
		if err != nil {
			result.Error = err.Error()
		}
		checkpoint("closed")
	}()
	runtime.GC()
	checkpoint("baseline")
	enabled = true
	for i := 0; i < 4; i++ {
		child = i + 1
		c := cpu()
		w := time.Now()
		d, e := sn.Fork(ctx)
		wall := float64(time.Since(w).Nanoseconds()) / 1e6
		used := cpu() - c
		if e != nil {
			return result, e
		}
		children = append(children, d)
		result.Children = append(result.Children, Child{wall, used})
		if observed {
			result.Stages = append(result.Stages, stageRecord(fmt.Sprintf("child%d_ready", child), current[:int(size.Load())], 0, 0))
		}

		if e = common.CheckChild(ctx, d, corrupt && i == 0); e != nil {
			return result, e
		}
		p, e := common.Connect(ctx, d)
		if e != nil {
			return result, e
		}
		_, e = p.ExecContext(ctx, "UPDATE fork_probe SET v=v+1 WHERE id=1")
		e = errors.Join(e, common.Disconnect(ctx, d, p))
		if e != nil {
			return result, e
		}
		checkpoint(fmt.Sprintf("child-%d", i+1))
	}
	for _, d := range children {
		p, e := common.Connect(ctx, d)
		if e != nil {
			return result, e
		}
		var n, total int
		e = p.QueryRowContext(ctx, "SELECT COUNT(*),SUM(v) FROM fork_probe").Scan(&n, &total)
		e = errors.Join(e, common.Disconnect(ctx, d, p))
		if e != nil {
			return result, e
		}
		if n != 1000 || total != 500501 {
			return result, fmt.Errorf("independent mutation oracle %d %d", n, total)
		}
	}
	return result, nil
}
func main() {
	out := flag.String("out", "", "result")
	bad := flag.Bool("corrupt", false, "negative oracle")
	observed := flag.Bool("observe", false, "stage observations")
	test := flag.Bool("selftest", false, "dirty-memory and initialization contracts")
	flag.Parse()
	if *test {
		if e := selftest(); e != nil {
			panic(e)
		}
		fmt.Println("SELFTEST PASS")
		return
	}
	r, e := run(*bad, *observed)
	data, _ := json.MarshalIndent(r, "", "  ")
	if err := os.WriteFile(*out, append(data, '\n'), 0600); err != nil {
		panic(err)
	}
	if e != nil || !r.Success {
		os.Exit(1)
	}
}

// resident() asks the OS about residency and never reads the guest pages.
type Stage struct {
	Name          string  `json:"name"`
	WallMS        float64 `json:"wall_ms"`
	CPUMS         float64 `json:"cpu_ms"`
	ResidentBytes int     `json:"resident_bytes"`
}

func stageRecord(name string, b []byte, wall, cpu float64) Stage {
	page := os.Getpagesize()
	vec := make([]byte, len(b)/page)
	_, _, e := syscall.Syscall(syscall.SYS_MINCORE, uintptr(unsafe.Pointer(unsafe.SliceData(b))), uintptr(len(b)), uintptr(unsafe.Pointer(unsafe.SliceData(vec))))
	runtime.KeepAlive(b)
	if e != 0 {
		panic(e)
	}
	n := 0
	for _, v := range vec {
		if v&1 != 0 {
			n += page
		}
	}
	checkpoint(name)
	return Stage{name, wall, cpu, n}
}
func selftest() error {
	const start, end = 15244864, 24227440
	for _, dirty := range []bool{false, true} {
		b, e := base.NewMemoryMapping(generated.InitialMemoryBytes, generated.InitialMemoryBytes)
		if e != nil {
			return e
		}
		memory := b.Bytes()
		if dirty {
			for i := start; i < end; i++ {
				memory[i] = 0xa5
			}
		}
		var m *base.Module
		if dirty {
			m = generated.NewWithMemory(nil, nil, nil, memory, generated.InitialMemoryBytes)
		} else {
			m = generated.NewWithFreshZeroMemory(nil, nil, nil, memory, generated.InitialMemoryBytes)
		}
		for i := start; i < end; i++ {
			if memory[i] != 0 {
				b.Close()
				return fmt.Errorf("zero contract dirty=%v at %d", dirty, i)
			}
		}
		if m.FreshZeroInit {
			b.Close()
			return fmt.Errorf("fresh capability leaked past initialization")
		}
		if e = checkData(memory); e != nil {
			b.Close()
			return e
		}
		if e = b.Close(); e != nil {
			return e
		}
	}
	stats := base.MemoryMappingStats()
	if stats["active_mappings"] != 0 || stats["active_rw_bytes"] != 0 || stats["active_reserved_bytes"] != 0 {
		return fmt.Errorf("selftest cleanup: %v", stats)
	}
	return nil
}

func checkData(memory []byte) error {
	if fmt.Sprintf("%x", sha256.Sum256(memory[8388608:14601702])) != "be973962467e1840edcf4e6fb48746545465c9c21af3f7f2f70e9f960c734b97" {
		return fmt.Errorf("data segment at 8388608")
	}
	if fmt.Sprintf("%x", sha256.Sum256(memory[14601728:15244348])) != "8fb1e5114c14bf018b8f74e21e7f8cd2fbef0faab141b2954537102af5b065aa" {
		return fmt.Errorf("data segment at 14601728")
	}
	if fmt.Sprintf("%x", sha256.Sum256(memory[15244352:15244857])) != "11982067548b495ef1cfdc73abf137051e80f65d5fc7e67b2339c434882bf9df" {
		return fmt.Errorf("data segment at 15244352")
	}
	return nil
}
