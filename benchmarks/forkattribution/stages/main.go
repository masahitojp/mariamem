// Stage observer is built only with the two recorded Go overlay files.
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"runtime"
	"sync"
	"sync/atomic"
	"syscall"
	"unsafe"

	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/forkattribution/common"
	"github.com/masahitojp/mariamem/internal/generatedgo"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

type Event struct {
	Stage         string            `json:"stage"`
	WallMS        float64           `json:"wall_ms"`
	CPUms         float64           `json:"cpu_ms"`
	HeapAlloc     uint64            `json:"heap_alloc_bytes"`
	TotalAlloc    uint64            `json:"total_alloc_bytes"`
	ResidentBytes int               `json:"guest_resident_bytes"`
	GuestBytes    int               `json:"guest_observed_bytes"`
	Mapping       map[string]uint64 `json:"mapping"`
}
type Comparison struct {
	PageBytes    int `json:"page_bytes"`
	BothResident int `json:"both_resident_pages"`
	OnlyFirst    int `json:"only_first_resident_pages"`
	OnlySecond   int `json:"only_second_resident_pages"`
	SameZero     int `json:"same_zero_pages"`
	SameNonzero  int `json:"same_nonzero_pages"`
	Different    int `json:"different_pages"`
}
type Result struct {
	Success    bool        `json:"success"`
	Cleanup    bool        `json:"cleanup_complete"`
	Events     []Event     `json:"events"`
	Comparison *Comparison `json:"comparison,omitempty"`
	Error      string      `json:"error,omitempty"`
}

func resident(b []byte) ([]byte, error) {
	if len(b) == 0 {
		return nil, nil
	}
	page := os.Getpagesize()
	if len(b)%page != 0 {
		return nil, errors.New("unaligned memory length")
	}
	vec := make([]byte, len(b)/page)
	_, _, e := syscall.Syscall(syscall.SYS_MINCORE, uintptr(unsafe.Pointer(unsafe.SliceData(b))), uintptr(len(b)), uintptr(unsafe.Pointer(unsafe.SliceData(vec))))
	runtime.KeepAlive(b)
	if e != 0 {
		return nil, e
	}
	return vec, nil
}
func compare(a, b []byte) (Comparison, error) {
	c := Comparison{PageBytes: os.Getpagesize()}

	av, e := resident(a)
	if e != nil {
		return c, e
	}
	bv, e := resident(b)
	if e != nil {
		return c, e
	}
	zero := make([]byte, c.PageBytes)
	for i := 0; i < max(len(av), len(bv)); i++ {
		ar, br := i < len(av) && av[i]&1 != 0, i < len(bv) && bv[i]&1 != 0
		switch {
		case ar && br:
			c.BothResident++
			aa, bb := a[i*c.PageBytes:(i+1)*c.PageBytes], b[i*c.PageBytes:(i+1)*c.PageBytes]
			if bytes.Equal(aa, bb) {
				if bytes.Equal(aa, zero) {
					c.SameZero++
				} else {
					c.SameNonzero++
				}
			} else {
				c.Different++
			}
		case ar:
			c.OnlyFirst++
		case br:
			c.OnlySecond++
		}
	}
	runtime.KeepAlive(a)
	runtime.KeepAlive(b)
	return c, nil
}
func selftest() error {
	page := os.Getpagesize()
	a, e := syscall.Mmap(-1, 0, page*2, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_ANON|syscall.MAP_PRIVATE)
	if e != nil {
		return e
	}
	defer syscall.Munmap(a)
	b, e := syscall.Mmap(-1, 0, page*2, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_ANON|syscall.MAP_PRIVATE)
	if e != nil {
		return e
	}
	defer syscall.Munmap(b)
	a[0] = 1
	b[0] = 1
	a[page] = 2
	b[page] = 3
	c, e := compare(a, b)
	if e != nil {
		return e
	}
	if c.BothResident != 2 || c.SameNonzero != 1 || c.Different != 1 {
		return fmt.Errorf("mincore/comparison oracle: %+v", c)
	}
	b[page] = 2
	c, e = compare(a, b)
	if e != nil {
		return e
	}
	if c.SameNonzero != 2 || c.Different != 0 {
		return fmt.Errorf("comparison mutation oracle: %+v", c)
	}
	return nil
}

var input = bufio.NewScanner(os.Stdin)
var result Result

func checkpoint(stage string, memory []byte, wall, cpu float64) error {
	vec, e := resident(memory)
	if e != nil {
		return e
	}
	pages := 0
	for _, v := range vec {
		if v&1 != 0 {
			pages++
		}
	}
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	event := Event{stage, wall, cpu, m.HeapAlloc, m.TotalAlloc, pages * os.Getpagesize(), len(memory), base.MemoryMappingStats()}
	result.Events = append(result.Events, event)
	if e = json.NewEncoder(os.Stdout).Encode(event); e != nil {
		return e
	}
	if !input.Scan() || input.Text() != "continue" {
		return errors.New("missing controller acknowledgement")
	}
	return nil
}
func run(corrupt bool) (err error) {
	if e := selftest(); e != nil {
		return e
	}
	ctx, cancel := common.Context()
	defer cancel()
	var mu sync.Mutex
	var current []byte
	var currentSize *atomic.Uint64
	var enabled atomic.Bool
	var child atomic.Int32
	generatedgo.AttributionHook = func(stage string, b []byte, size *atomic.Uint64, wall, cpu float64) {
		mu.Lock()
		current = b
		currentSize = size
		mu.Unlock()
		if size != nil {
			b = b[:int(size.Load())]
		}
		if enabled.Load() {
			if e := checkpoint(fmt.Sprintf("child%d_%s", child.Load(), stage), b, wall, cpu); e != nil {
				panic(e)
			}
		}
	}
	defer func() { generatedgo.AttributionHook = nil }()
	sn, e := common.Prepare(ctx)
	if e != nil {
		return e
	}
	var children []*mariamem.Database
	defer func() {
		e := sn.Close()
		for _, d := range children {
			e = errors.Join(e, d.Close())
		}
		result.Cleanup = e == nil
		err = errors.Join(err, e)
	}()
	runtime.GC()
	if e = checkpoint("baseline", nil, 0, 0); e != nil {
		return e
	}
	var memories [][]byte
	enabled.Store(true)
	for i := 1; i <= 2; i++ {
		child.Store(int32(i))
		d, e := sn.Fork(ctx)
		if e != nil {
			return e
		}
		children = append(children, d)
		mu.Lock()
		memory := current[:int(currentSize.Load())]
		mu.Unlock()

		if e = checkpoint(fmt.Sprintf("child%d_ready", i), memory, 0, 0); e != nil {
			return e
		}
		if e = common.CheckChild(ctx, d, corrupt); e != nil {
			return e
		}
		mu.Lock()
		memory = current[:int(currentSize.Load())]
		mu.Unlock()
		memories = append(memories, memory)
		if e = checkpoint(fmt.Sprintf("child%d_checked", i), memory, 0, 0); e != nil {
			return e
		}
	}
	enabled.Store(false)
	// Freeze no guest state: sample existing resident pages only, outside all timing claims.
	comparison, e := compare(memories[0], memories[1])
	if e != nil {
		return e
	}
	result.Comparison = &comparison
	if e = checkpoint("after_content_comparison", memories[1], 0, 0); e != nil {
		return e
	}
	// Check independent mutation and retained baseline after read-only observation.
	for i, d := range children {
		p, e := common.Connect(ctx, d)
		if e != nil {
			return e
		}
		_, e = p.ExecContext(ctx, fmt.Sprintf("UPDATE fork_probe SET v=%d WHERE id=1", -i-1))
		e = errors.Join(e, common.Disconnect(ctx, d, p))
		if e != nil {
			return e
		}
	}
	for i, d := range children {
		p, e := common.Connect(ctx, d)
		if e != nil {
			return e
		}
		var v int
		e = p.QueryRowContext(ctx, "SELECT v FROM fork_probe WHERE id=1").Scan(&v)
		e = errors.Join(e, common.Disconnect(ctx, d, p))
		if e != nil {
			return e
		}
		if v != -i-1 {
			return fmt.Errorf("isolation child%d value%d", i+1, v)
		}
	}
	memories = nil
	mu.Lock()
	current = nil
	mu.Unlock()
	for _, d := range children {
		if e = d.Close(); e != nil {
			return e
		}
	}
	children = nil
	if e = checkpoint("closed_children", nil, 0, 0); e != nil {
		return e
	}
	d, e := sn.Fork(ctx)
	if e != nil {
		return e
	}
	e = common.CheckChild(ctx, d, false)
	e = errors.Join(e, d.Close())
	if e != nil {
		return e
	}
	mu.Lock()
	current = nil
	mu.Unlock()
	return nil
}
func main() {
	out := flag.String("out", "", "report")
	corrupt := flag.Bool("corrupt", false, "negative oracle")
	flag.Parse()
	if *out == "" || runtime.GOOS != "darwin" {
		panic("Darwin only and -out required")
	}
	e := run(*corrupt)
	result.Success = e == nil
	if e != nil {
		result.Error = e.Error()
	}
	data, j := json.MarshalIndent(result, "", "  ")
	if j == nil {
		j = os.WriteFile(*out, append(data, '\n'), 0600)
	}
	if e != nil || j != nil {
		fmt.Fprintln(os.Stderr, errors.Join(e, j))
		os.Exit(1)
	}
}
