//go:build (darwin && arm64) || (linux && amd64)

// Package image owns the process-local immutable initial-memory image.
package image

import (
	"bytes"
	_ "embed"
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/generatedgo/imagelayout"
	"os"
	"sync"
	"syscall"
	"time"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

const maximum = 2 << 30

//go:embed layout.json
var layoutJSON []byte

var errClosed = errors.New("static image factory closed")

// cleanupOwner is implemented by base.MemoryReleaseError; retain retry authority.
type cleanupOwner interface {
	error
	Close() error
}

type factory struct {
	layout            imagelayout.Layout
	layoutErr         error
	fullScan          bool
	scannedBytes      int
	constructorMS     float64
	scanMS            float64
	ranges            []base.ImageRange
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
	debt              interface{ Close() error }
}

func newFactory(dir string) *factory {
	f := &factory{dir: dir, closeFile: (*os.File).Close, openRead: os.Open}
	f.mapImage = func(fd int, initial, maximum uint64) (*base.MemoryMapping, error) {
		return base.NewStaticPageMapping(fd, initial, maximum, f.ranges)
	}
	return f
}

func (f *factory) build() (err error) {
	f.builds++
	if f.layout.Version == 0 && f.layoutErr == nil {
		f.layout, f.layoutErr = imagelayout.Decode(layoutJSON)
	}
	if f.layoutErr != nil {
		return f.layoutErr
	}
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
	f.dropped = make([]bool, len(m.DataSegs))
	for i, data := range m.DataSegs {
		f.dropped[i] = data == nil
	}
	if !f.layout.MatchesState(generated.InitialMemoryBytes, f.globals, f.dataEnd, f.dropped) {
		return errors.New("generated initial-image metadata differs; regenerate and review")
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
	// Generated from complete constructor bytes, independent of the host page size.
	begin, finish, err := f.layout.Bounds(uint64(page))
	if err != nil {
		return err
	}
	start, end := int(begin), int(finish)
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
		f.buildErr = f.buildSafely()
		f.buildMS = float64(time.Since(at)) / 1e6
	}
	if f.buildErr != nil {
		return nil, errors.Join(f.buildErr, f.disposeLocked())
	} // No fallback or hidden retry.
	if !f.layout.MatchesState(generated.InitialMemoryBytes, f.globals, f.dataEnd, f.dropped) {
		return nil, errors.New("invalid image metadata")
	}
	b, err := f.mapImage(int(f.image.Fd()), generated.InitialMemoryBytes, maximum)
	if err != nil {
		var debt cleanupOwner
		if errors.As(err, &debt) {
			f.debt = debt
			f.buildErr = err
			return nil, errors.Join(err, f.disposeLocked())
		}
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

// There is one cache per compiled engine in this process. Only immutable initial
// bytes are retained; DB Close still joins workers and disposes the child mapping.
var processImage = newFactory("")

// Acquire creates a private module using the lazily built process image.
func Acquire(wasi base.Wasi_snapshot_preview1Imports, wasix base.Wasix_32v1Imports) (*base.Module, func() error, error) {
	return processImage.acquireForHost(wasi, wasix)
}

// Stats separates the deliberately retained process image from child ownership.
func Stats() map[string]any { return processImage.Stats() }

func (f *factory) acquireForHost(wasi base.Wasi_snapshot_preview1Imports, wasix base.Wasix_32v1Imports) (*base.Module, func() error, error) {
	c, e := f.acquire()
	if e != nil {
		return nil, nil, e
	}
	c.m.Wasi_snapshot_preview1 = wasi
	c.m.Wasix_32v1 = wasix
	return c.m, c.backing.Close, nil
}
func (f *factory) Stats() map[string]any {
	f.mu.Lock()
	defer f.mu.Unlock()
	v := map[string]any{"builds": f.builds, "build_ms": f.buildMS, "acquires": f.acquires, "closed": f.closed, "owned_fds": len(f.files)}
	v["process_lifetime"] = true
	v["failed"] = f.buildErr != nil
	v["cleanup_debt"] = f.debt != nil || f.path != "" || (f.buildErr != nil && len(f.files) != 0)
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
	f.closed = true // Only explicitly owned test factories close; process cache has no public close.
	return f.disposeLocked()
}

func (f *factory) disposeLocked() error {
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

// A constructor panic cannot leave the cache looking successfully initialized.
func (f *factory) buildSafely() (err error) {
	defer func() {
		if p := recover(); p != nil {
			if e, ok := p.(error); ok {
				err = e
			} else {
				err = fmt.Errorf("initial image constructor: %v", p)
			}
		}
		var debt cleanupOwner
		if errors.As(err, &debt) && f.debt == nil {
			f.debt = debt
		}
	}()
	return f.build()
}
