package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/zerofill/common"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

type Totals struct {
	Calls     uint64 `json:"calls"`
	Bytes     uint64 `json:"bytes"`
	ZeroCalls uint64 `json:"zero_calls"`
	ZeroBytes uint64 `json:"zero_bytes"`
	ZeroNS    int64  `json:"zero_ns"`
	NonzeroNS int64  `json:"nonzero_ns"`
}
type Frame struct {
	Function string `json:"function"`
	File     string `json:"file"`
	Line     int    `json:"line"`
}
type Event struct {
	Phase uint32  `json:"phase"`
	Dst   uint32  `json:"dst"`
	Bytes uint32  `json:"bytes"`
	NS    int64   `json:"ns"`
	Stack []Frame `json:"stack"`
}
type Meter struct {
	sync.Mutex
	Totals   map[uint32]*Totals
	Events   []Event
	Overflow bool
}

var meter = Meter{Totals: map[uint32]*Totals{}}

func observe(m *base.Module, phase, dst uint32, v byte, n uint32, d time.Duration) {
	var stack []Frame
	if v == 0 && n >= 65536 {
		var pcs [8]uintptr
		k := runtime.Callers(2, pcs[:])
		frames := runtime.CallersFrames(pcs[:k])
		for {
			f, more := frames.Next()
			file := f.File
			if i := strings.Index(file, "github.com/masahitojp/mariamem/"); i >= 0 {
				file = file[i:]
			}
			stack = append(stack, Frame{f.Function, file, f.Line})
			if !more {
				break
			}
		}
	}
	meter.Lock()
	defer meter.Unlock()
	t := meter.Totals[phase]
	if t == nil {
		t = &Totals{}
		meter.Totals[phase] = t
	}
	t.Calls++
	t.Bytes += uint64(n)
	if v == 0 {
		t.ZeroCalls++
		t.ZeroBytes += uint64(n)
		t.ZeroNS += int64(d)
	} else {
		t.NonzeroNS += int64(d)
	}
	if len(stack) > 0 {
		if len(meter.Events) >= 20000 {
			meter.Overflow = true
		} else {
			meter.Events = append(meter.Events, Event{phase, dst, n, int64(d), stack})
		}
	}
}

type Usage struct {
	CPUms float64
	Minor int64
	Major int64
}

func usage() Usage {
	var r syscall.Rusage
	if e := syscall.Getrusage(syscall.RUSAGE_SELF, &r); e != nil {
		panic(e)
	}
	return Usage{float64(r.Utime.Sec+r.Stime.Sec)*1000 + float64(r.Utime.Usec+r.Stime.Usec)/1000, r.Minflt, r.Majflt}
}

type Phase struct {
	ID     uint32  `json:"id"`
	Name   string  `json:"name"`
	WallMS float64 `json:"wall_ms"`
	CPUMS  float64 `json:"cpu_ms"`
	Minor  int64   `json:"minor_faults"`
	Major  int64   `json:"major_faults"`
}
type Result struct {
	Observed bool               `json:"observed"`
	Success  bool               `json:"success"`
	Error    string             `json:"error,omitempty"`
	Cleanup  bool               `json:"cleanup"`
	Phases   []Phase            `json:"phases"`
	Totals   map[uint32]*Totals `json:"totals"`
	Events   []Event            `json:"large_zero_events"`
	Overflow bool               `json:"overflow"`
	Final    map[string]uint64  `json:"final"`
}

func run(observed, bad bool) (result Result, err error) {
	result.Observed = observed
	if observed {
		base.FillObserver = observe
	}
	ctx, cancel := common.Context()
	defer cancel()
	phase := func(id uint32, name string, fn func() error) error {
		base.FillPhase.Store(id)
		u := usage()
		t := time.Now()
		e := fn()
		wall := time.Since(t)
		v := usage()
		result.Phases = append(result.Phases, Phase{id, name, float64(wall.Nanoseconds()) / 1e6, v.CPUms - u.CPUms, v.Minor - u.Minor, v.Major - u.Major})
		return e
	}
	defer func() {
		result.Final = base.MemoryMappingStats()
		result.Cleanup = result.Final["active_mappings"] == 0
		meter.Lock()
		result.Totals = meter.Totals
		result.Events = meter.Events
		result.Overflow = meter.Overflow
		meter.Unlock()
		result.Success = err == nil && result.Cleanup && !result.Overflow
		if err != nil {
			result.Error = err.Error()
		}
	}()
	base.FillPhase.Store(0)
	sn, e := common.Prepare(ctx)
	if e != nil {
		return result, e
	}
	defer func() { err = errors.Join(err, sn.Close()) }()
	for i := 0; i < 2; i++ {
		id := uint32(1 + i*3)
		e = func() (err error) {
			var d *mariamem.Database
			err = phase(id, "fork", func() error { var x error; d, x = sn.Fork(ctx); return x })
			if err != nil {
				return err
			}
			defer func() { err = errors.Join(err, phase(id+2, "close", d.Close)) }()
			return phase(id+1, "verify", func() error {
				if x := common.CheckChild(ctx, d, bad && i == 0); x != nil {
					return x
				}
				p, x := common.Connect(ctx, d)
				if x != nil {
					return x
				}
				_, x = p.ExecContext(ctx, "UPDATE fork_probe SET v=v+1 WHERE id=1")
				if x == nil {
					var total int
					x = p.QueryRowContext(ctx, "SELECT SUM(v) FROM fork_probe").Scan(&total)
					if x == nil && total != 500501 {
						x = fmt.Errorf("mutation oracle: %d", total)
					}
				}
				return errors.Join(x, common.Disconnect(ctx, d, p))
			})
		}()
		if e != nil {
			return result, e
		}
	}
	return result, nil
}
func selftest() error {
	// Validate observer values without executing a guest or reading uninitialized pages.
	m := &base.Module{}
	m.Memory = make([]byte, 2*65536)
	m.MemSize = newAtomic(uint64(len(m.Memory)))
	base.FillObserver = observe
	base.FillPhase.Store(99)
	base.MemoryFill(m, 0, 0, 65536)
	base.MemoryFill(m, 65536, 7, 4)
	base.MemoryFill(m, 0, 0, 0)
	t := meter.Totals[99]
	if t == nil || t.Calls != 2 || t.ZeroCalls != 1 || t.ZeroBytes != 65536 || t.Bytes != 65540 || len(meter.Events) != 1 || m.Memory[65536] != 7 {
		return fmt.Errorf("observer selftest")
	}
	trapped := false
	func() { defer func() { trapped = recover() != nil }(); base.MemoryFill(m, int32(len(m.Memory)), 0, 1) }()
	if !trapped || t.Calls != 2 {
		return fmt.Errorf("bounds observer")
	}
	return nil
}
func main() {
	out := flag.String("out", "", "report")
	observed := flag.Bool("observe", false, "enable observer")
	bad := flag.Bool("corrupt", false, "negative SQL oracle")
	test := flag.Bool("selftest", false, "observer fixture")
	flag.Parse()
	if *test {
		if e := selftest(); e != nil {
			panic(e)
		}
		fmt.Println("SELFTEST PASS")
		return
	}
	r, e := run(*observed, *bad)
	data, _ := json.MarshalIndent(r, "", "  ")
	if x := os.WriteFile(*out, append(data, '\n'), 0600); x != nil {
		panic(x)
	}
	if e != nil || !r.Success {
		os.Exit(1)
	}
}

func newAtomic(v uint64) *atomic.Uint64 { p := new(atomic.Uint64); p.Store(v); return p }
