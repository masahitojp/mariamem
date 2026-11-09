//go:build (darwin && arm64) || (linux && amd64)

// Package staticimage is an Issue123 constructor-only experiment, not a product API.
package staticimage

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"sync"
	"syscall"
	"time"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

const maximum = 2 << 30

var errClosed = errors.New("static image factory closed")

type factory struct {
	fullScan          bool
	scannedBytes      int
	constructorMS     float64
	scanMS            float64
	ranges            []base.ImageRange
	pageOnly          bool
	buildMS           float64
	acquires          int
	mu                sync.Mutex
	dir               string
	attempted, closed bool
	builds            int
	buildErr          error
	files             []*os.File // Includes unpublished owners until confirmed close.
	path              string
	image             *os.File
	globals           []uint64
	dataEnd           uint32
	dropped           []bool
	closeFile         func(*os.File) error
	beforeBuild       func() error
	openRead          func(string) (*os.File, error)
	mapImage          func(int, uint64, uint64) (*base.MemoryMapping, error)
	debt              *base.MemoryMapping
}

func newFactory(dir string) *factory {
	f := &factory{dir: dir, closeFile: (*os.File).Close, openRead: os.Open,
		pageOnly: true, fullScan: os.Getenv("MARIAMEM_IMAGE_FULL_SCAN") == "1"}
	if f.pageOnly {
		f.mapImage = func(fd int, initial, maximum uint64) (*base.MemoryMapping, error) {
			return base.NewStaticPageMapping(fd, initial, maximum, f.ranges)
		}
	}
	return f
}

func (f *factory) build() (err error) {
	f.builds++
	if f.beforeBuild != nil {
		if err = f.beforeBuild(); err != nil {
			return err
		}
	}
	b, err := base.NewMemoryMapping(generated.InitialMemoryBytes, maximum)
	if err != nil {
		return err
	}
	defer func() {
		if e := b.Close(); e != nil {
			f.debt = b
			err = errors.Join(err, e)
		}
	}()
	// Only generated data initialization. No Start/WasmCallCtors/engine execution.
	constructorAt := time.Now()
	m := generated.NewWithMemory(nil, nil, nil, b.Bytes(), generated.InitialMemoryBytes)
	f.constructorMS = float64(time.Since(constructorAt)) / 1e6
	f.globals, f.dataEnd = base.SaveGlobals(m), m.DataEnd
	if len(f.globals) != 2 || f.globals[0] != 8388608 || f.globals[1] != 18012928 || f.dataEnd != 18013433 {
		return errors.New("pinned guest layout mismatch")
	}
	f.dropped = make([]bool, len(m.DataSegs))
	for i, data := range m.DataSegs {
		f.dropped[i] = data == nil
	}
	w, err := os.CreateTemp(f.dir, "static-image-")
	if err != nil {
		return err
	}
	f.path, f.files = w.Name(), append(f.files, w)
	if err = w.Truncate(maximum); err != nil {
		return err
	}
	page := os.Getpagesize()
	zero := make([]byte, page)
	// Pinned Fn67 is the only linear-memory writer in NewWithMemory.
	// Include its zero-fill and 4-byte init flag, not just DataEnd.
	// Source hashes and whole-memory equality are enforced by the experiment.
	start, end := 8388608/page*page, (26996020+page-1)/page*page
	if f.fullScan {
		start, end = 0, generated.InitialMemoryBytes
	}
	f.scannedBytes = end - start
	scanAt := time.Now()
	for off := start; off < end; off += page {
		data := m.Memory[off : off+page]
		if !bytes.Equal(data, zero) {
			n := len(f.ranges)
			if n > 0 && f.ranges[n-1].Offset+f.ranges[n-1].Length == uint64(off) {
				f.ranges[n-1].Length += uint64(page)
			} else {
				f.ranges = append(f.ranges, base.ImageRange{Offset: uint64(off), Length: uint64(page)})
			}
			if _, err = w.WriteAt(data, int64(off)); err != nil {
				return err
			}
		}
	}
	f.scanMS = float64(time.Since(scanAt)) / 1e6
	r, err := f.openRead(f.path)
	if err != nil {
		return err
	}
	f.files = append(f.files, r)
	if err = f.closeFile(w); err != nil {
		return err
	}
	f.files = []*os.File{r}
	if err = os.Remove(f.path); err != nil {
		return err
	}
	f.path = ""
	f.image = r
	return nil
}

type child struct {
	m       *base.Module
	backing *base.MemoryMapping
}

func (f *factory) acquire() (*child, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.closed {
		return nil, errClosed
	}
	if !f.attempted {
		f.attempted = true
		at := time.Now()
		f.buildErr = f.build()
		f.buildMS = float64(time.Since(at)) / 1e6
	}
	if f.buildErr != nil {
		return nil, f.buildErr
	} // No fallback or hidden retry.
	if len(f.globals) != 2 || len(f.dropped) != 3 {
		return nil, errors.New("invalid image metadata")
	}
	b, err := f.mapImage(int(f.image.Fd()), generated.InitialMemoryBytes, maximum)
	if err != nil {
		return nil, err
	}
	transferred := false
	defer func() {
		if !transferred {
			e := b.Close()
			if e != nil {
				f.debt = b
				f.buildErr = e
			}
			if p := recover(); p != nil {
				panic(errors.Join(fmt.Errorf("image constructor: %v", p), e))
			}
		}
	}()
	m := generated.NewFromSnapshot(nil, nil, nil, b.Bytes(), generated.InitialMemoryBytes, f.globals)
	m.DataEnd = f.dataEnd
	for i, dropped := range f.dropped {
		if dropped {
			base.DataDrop(m, i)
		}
	}
	m.PrepareMemoryGrow = b.Grow
	transferred = true
	f.acquires++
	return &child{m, b}, nil
}

// Experiment-only adapter. The image never retains the host of an earlier DB.
func NewEngineFactory(dir string) *factory { return newFactory(dir) }
func (f *factory) AcquireForHost(wasi base.Wasi_snapshot_preview1Imports, wasix base.Wasix_32v1Imports) (*base.Module, func() error, error) {
	c, e := f.acquire()
	if e != nil {
		return nil, nil, e
	}
	c.m.Wasi_snapshot_preview1 = wasi
	c.m.Wasix_32v1 = wasix
	return c.m, c.backing.Close, nil
}
func (f *factory) Close() error { return f.close() }
func (f *factory) Stats() map[string]any {
	f.mu.Lock()
	defer f.mu.Unlock()
	v := map[string]any{"builds": f.builds, "build_ms": f.buildMS, "acquires": f.acquires, "closed": f.closed, "owned_fds": len(f.files)}
	v["page_only"] = f.pageOnly
	v["full_scan"] = f.fullScan
	v["scanned_bytes"] = f.scannedBytes
	v["constructor_ms"] = f.constructorMS
	v["scan_ms"] = f.scanMS
	v["page_size"] = os.Getpagesize()
	v["image_ranges"] = append([]base.ImageRange(nil), f.ranges...)
	var mapped uint64
	for _, r := range f.ranges {
		mapped += r.Length
	}
	v["initialized_page_bytes"] = mapped
	if f.image != nil && !f.closed {
		var st syscall.Stat_t
		if syscall.Fstat(int(f.image.Fd()), &st) == nil {
			v["image_logical_bytes"] = st.Size
			v["image_allocated_bytes"] = st.Blocks * 512
		}
	}
	return v
}

func (c *child) close() error {
	p := c.m.Threads.WaitThreads()
	err := c.backing.Close()
	if p != nil {
		err = errors.Join(fmt.Errorf("worker: %v", p), err)
	}
	return err
}

func (f *factory) close() error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.closed = true // A cleanup retry never reopens admission.
	var err error
	var retained []*os.File
	for _, file := range f.files {
		if e := f.closeFile(file); e != nil {
			retained = append(retained, file)
			err = errors.Join(err, e)
		}
	}
	f.files = retained
	if f.path != "" {
		if e := os.Remove(f.path); e != nil {
			err = errors.Join(err, e)
		} else {
			f.path = ""
		}
	}
	if f.debt != nil {
		if e := f.debt.Close(); e != nil {
			err = errors.Join(err, e)
		} else {
			f.debt = nil
		}
	}
	return err
}
