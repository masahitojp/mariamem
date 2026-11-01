package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/bufferalignment/common"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"runtime"
	"strings"
	"sync"
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

type Child struct {
	WallMS float64 `json:"wall_ms"`
	CPUMS  float64 `json:"cpu_ms"`
}
type Result struct {
	Observed bool               `json:"observed"`
	Totals   map[uint32]*Totals `json:"totals"`
	Events   []Event            `json:"large_zero_events"`
	Overflow bool               `json:"overflow"`
	Success  bool               `json:"success"`
	Error    string             `json:"error,omitempty"`
	Cleanup  bool               `json:"cleanup"`
	Children []Child            `json:"children"`
	Final    map[string]uint64  `json:"final"`
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
	if observed {
		base.FillObserver = observe
	}
	ctx, cancel := common.Context()
	defer cancel()
	var children []*mariamem.Database
	sn, e := common.Prepare(ctx)
	if e != nil {
		return result, e
	}
	defer func() {
		base.FillPhase.Store(99)
		for _, d := range children {
			err = errors.Join(err, d.Close())
		}
		err = errors.Join(err, sn.Close())
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
		checkpoint("closed")
	}()
	runtime.GC()
	checkpoint("baseline")
	for i := 0; i < 4; i++ {
		base.FillPhase.Store(uint32(i + 1))
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
		base.FillPhase.Store(uint32(i + 11))
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
	observed := flag.Bool("observe", false, "trace large zero fills")
	flag.Parse()
	r, e := run(*bad, *observed)
	data, _ := json.MarshalIndent(r, "", "  ")
	if err := os.WriteFile(*out, append(data, '\n'), 0600); err != nil {
		panic(err)
	}
	if e != nil || !r.Success {
		os.Exit(1)
	}
}
