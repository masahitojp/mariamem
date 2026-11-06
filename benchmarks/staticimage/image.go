//go:build (darwin && arm64) || (linux && amd64)

// Package staticimage is an Issue123 constructor-only experiment, not a product API.
package staticimage

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"sync"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

const maximum = 2 << 30

var errClosed = errors.New("static image factory closed")

type factory struct {
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
	return &factory{dir: dir, closeFile: (*os.File).Close, openRead: os.Open,
		mapImage: base.NewStaticImageMapping}
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
	m := generated.NewWithMemory(nil, nil, nil, b.Bytes(), generated.InitialMemoryBytes)
	f.globals, f.dataEnd = base.SaveGlobals(m), m.DataEnd
	if len(f.globals) != 2 || f.globals[0] != 8388608 || f.globals[1] != 17998464 || f.dataEnd != 17998969 {
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
	for off := 0; off < generated.InitialMemoryBytes; off += page {
		data := m.Memory[off : off+page]
		if !bytes.Equal(data, zero) {
			if _, err = w.WriteAt(data, int64(off)); err != nil {
				return err
			}
		}
	}
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
		f.buildErr = f.build()
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
	return &child{m, b}, nil
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
