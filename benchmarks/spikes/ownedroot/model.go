// Package ownedroot is a guest-disconnected ownership experiment, not runtime code.
package ownedroot

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"io"
	"path"
	"sort"
	"sync"
)

const BlockSize = 16 * 1024

// Counts describe actual payload helpers, separately from metadata work.
type Counts struct {
	ReadBytes, CopyBytes, HashBytes, ZeroBytes, WriteBytes, AllocBytes, Metadata int64
}
type Meter struct {
	mu     sync.Mutex
	values map[string]Counts
}

func NewMeter() *Meter { return &Meter{values: map[string]Counts{}} }
func (m *Meter) add(phase, route string, v Counts) {
	m.mu.Lock()
	defer m.mu.Unlock()
	k := phase + "/" + route
	a := m.values[k]
	a.ReadBytes += v.ReadBytes
	a.CopyBytes += v.CopyBytes
	a.HashBytes += v.HashBytes
	a.ZeroBytes += v.ZeroBytes
	a.WriteBytes += v.WriteBytes
	a.AllocBytes += v.AllocBytes
	a.Metadata += v.Metadata
	m.values[k] = a
}
func (m *Meter) Snapshot() map[string]Counts {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := map[string]Counts{}
	for k, v := range m.values {
		out[k] = v
	}
	return out
}
func (m *Meter) copy(phase, route string, dst, src []byte) {
	n := copy(dst, src)
	m.add(phase, route, Counts{ReadBytes: int64(n), CopyBytes: int64(n)})
}
func (m *Meter) zero(phase, route string, dst []byte) {
	clear(dst)
	m.add(phase, route, Counts{ZeroBytes: int64(len(dst))})
}
func (m *Meter) hash(phase, route string, p []byte) string {
	m.add(phase, route, Counts{ReadBytes: int64(len(p)), HashBytes: int64(len(p))})
	return fmt.Sprintf("%x", sha256.Sum256(p))
}
func (m *Meter) alloc(phase, route string) *block {
	m.add(phase, route, Counts{AllocBytes: BlockSize, ZeroBytes: BlockSize})
	return new(block)
}

type block struct{ data [BlockSize]byte }
type entry struct {
	block    *block
	valid    int
	writable bool
	route    string
}
type file struct {
	size   int64
	blocks map[int64]entry
}
type stamp struct {
	file   *file
	size   int64
	blocks map[int64]entry
}
type captureKey struct{ value byte }
type root struct {
	key         *captureKey
	build       string
	files       map[string]*file
	dirs        map[string]bool
	sealed      bool
	manifest    map[string]stamp
	dirManifest map[string]bool
}
type Builder struct {
	mu         sync.Mutex
	r          *root
	meter      *Meter
	writePhase string
}

func New(build string, m *Meter) *Builder {
	return &Builder{r: &root{build: build, files: map[string]*file{}, dirs: map[string]bool{".": true}}, meter: m, writePhase: "write"}
}
func validName(n string) bool {
	return n != "" && n != "." && !path.IsAbs(n) && path.Clean(n) == n && n != ".." && len(n) > 0 && !(len(n) > 3 && n[:3] == "../")
}
func (b *Builder) mutable() error {
	if b.r == nil || b.r.sealed {
		return errors.New("writer closed")
	}
	return nil
}

type Handle struct {
	b   *Builder
	f   *file
	off int64
}

func (b *Builder) Open(name string) (*Handle, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if err := b.mutable(); err != nil {
		return nil, err
	}
	if !validName(name) {
		return nil, errors.New("invalid path")
	}
	f := b.r.files[name]
	if f == nil {
		if b.r.dirs[name] {
			return nil, errors.New("directory collision")
		}
		for p := path.Dir(name); p != "."; p = path.Dir(p) {
			if b.r.files[p] != nil {
				return nil, errors.New("file parent")
			}
		}
		f = &file{blocks: map[int64]entry{}}
		b.r.files[name] = f
		for p := path.Dir(name); p != "."; p = path.Dir(p) {
			b.r.dirs[p] = true
		}
	}
	return &Handle{b: b, f: f}, nil
}
func (b *Builder) OpenRelative(dir, name string) (*Handle, error) {
	return b.Open(path.Join(dir, name))
}
func (h *Handle) Close() { h.b.mu.Lock(); defer h.b.mu.Unlock(); h.f = nil }
func (h *Handle) active() error {
	if h.f == nil {
		return errors.New("handle closed")
	}
	return h.b.mutable()
}
func (h *Handle) WriteAt(p []byte, off int64) error {
	h.b.mu.Lock()
	defer h.b.mu.Unlock()
	if e := h.active(); e != nil {
		return e
	}
	return h.write(p, off)
}
func (h *Handle) write(p []byte, off int64) error {
	if off < 0 || int64(len(p)) > int64(^uint64(0)>>1)-off {
		return errors.New("range overflow")
	}
	if len(p) == 0 {
		return nil
	}
	for done := 0; done < len(p); {
		at := off + int64(done)
		index := at / BlockSize
		in := int(at % BlockSize)
		n := min(len(p)-done, BlockSize-in)
		e := h.f.blocks[index]
		if !e.writable {
			fresh := h.b.meter.alloc(h.b.writePhase, "dirty")
			if e.block != nil {
				h.b.meter.copy(h.b.writePhase, "inherited", fresh.data[:e.valid], e.block.data[:e.valid])
			}
			e = entry{block: fresh, valid: e.valid, writable: true, route: "dirty"}
		}
		if in > e.valid {
			h.b.meter.zero(h.b.writePhase, "dirty", e.block.data[e.valid:in])
		}
		h.b.meter.copy(h.b.writePhase, "dirty", e.block.data[in:in+n], p[done:done+n])
		h.b.meter.add(h.b.writePhase, "dirty", Counts{WriteBytes: int64(n)})
		e.valid = max(e.valid, in+n)
		h.f.blocks[index] = e
		done += n
	}
	h.f.size = max(h.f.size, off+int64(len(p)))
	return nil
}
func (h *Handle) Append(p []byte) error {
	h.b.mu.Lock()
	defer h.b.mu.Unlock()
	if e := h.active(); e != nil {
		return e
	}
	return h.write(p, h.f.size)
}
func (h *Handle) Truncate(n int64) error {
	h.b.mu.Lock()
	defer h.b.mu.Unlock()
	if e := h.active(); e != nil {
		return e
	}
	return h.resize(n)
}
func (h *Handle) resize(n int64) error {
	if n < 0 {
		return errors.New("negative size")
	}
	if n < h.f.size {
		for i, e := range h.f.blocks {
			if i >= n/BlockSize && (i > n/BlockSize || n%BlockSize == 0) {
				delete(h.f.blocks, i)
			} else if i == n/BlockSize {
				e.valid = min(e.valid, int(n%BlockSize))
				h.f.blocks[i] = e
			}
		}
	}
	h.f.size = n
	return nil
}
func (h *Handle) Allocate(n int64) error {
	h.b.mu.Lock()
	defer h.b.mu.Unlock()
	if e := h.active(); e != nil {
		return e
	}
	if n < 0 {
		return errors.New("negative size")
	}
	if n > h.f.size {
		return h.resize(n)
	}
	return nil
}
func (b *Builder) Rename(from, to string) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if e := b.mutable(); e != nil {
		return e
	}
	if !validName(to) || path.Dir(from) != path.Dir(to) || b.r.files[from] == nil || b.r.dirs[to] {
		return errors.New("unsupported rename")
	}
	b.r.files[to] = b.r.files[from]
	delete(b.r.files, from)
	return nil
}
func (b *Builder) Remove(name string) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if e := b.mutable(); e != nil {
		return e
	}
	if b.r.files[name] == nil {
		return errors.New("missing file")
	}
	delete(b.r.files, name)
	return nil
}
func readFile(f *file, p []byte, off int64, m *Meter, phase string) (int, error) {
	if off < 0 {
		return 0, errors.New("negative offset")
	}
	if len(p) == 0 {
		return 0, nil
	}
	if off >= f.size {
		return 0, io.EOF
	}
	count := int(min(int64(len(p)), f.size-off))
	for done := 0; done < count; {
		at := off + int64(done)
		in := int(at % BlockSize)
		n := min(count-done, BlockSize-in)
		e := f.blocks[at/BlockSize]
		out := p[done : done+n]
		if e.block == nil || in >= e.valid {
			m.zero(phase, "zero", out)
		} else {
			nc := min(n, e.valid-in)
			m.copy(phase, e.route, out[:nc], e.block.data[in:in+nc])
			if nc < n {
				m.zero(phase, "zero", out[nc:])
			}
		}
		done += n
	}
	if count < len(p) {
		return count, io.EOF
	}
	return count, nil
}
func (b *Builder) ReadAt(name string, p []byte, off int64) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if e := b.mutable(); e != nil {
		return 0, e
	}
	f := b.r.files[name]
	if f == nil {
		return 0, errors.New("missing file")
	}
	return readFile(f, p, off, b.meter, "application-read")
}

// Capture is bound to this exact root before freezing. No arbitrary root constructor is exported.
type Capture struct {
	mu               sync.Mutex
	expected, result *root
	key              *captureKey
	abandoned, taken bool
}

func (b *Builder) Request() (*Capture, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if e := b.mutable(); e != nil {
		return nil, e
	}
	if b.r.key != nil {
		return nil, errors.New("capture already requested")
	}
	k := &captureKey{1}
	b.r.key = k
	return &Capture{expected: b.r, key: k}, nil
}
func (c *Capture) Discard() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.abandoned = true
	c.expected = nil
	c.result = nil
}
func (b *Builder) Freeze(c *Capture, failAfter int) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	c.mu.Lock()
	defer c.mu.Unlock()
	if e := b.mutable(); e != nil {
		return e
	}
	if c.expected != b.r || c.key != b.r.key || c.abandoned || c.taken {
		return errors.New("capture mismatch")
	}
	r := b.r
	r.sealed = true
	b.r = nil
	r.manifest = map[string]stamp{}
	r.dirManifest = map[string]bool{}
	fail := func() error {
		c.expected = nil
		c.result = nil
		c.abandoned = true
		return errors.New("injected freeze failure")
	}
	if failAfter == 0 {
		return fail()
	}
	for n := range r.dirs {
		r.dirManifest[n] = true
		b.meter.add("freeze", "metadata", Counts{Metadata: 1})
	}
	for n, f := range r.files {
		s := stamp{file: f, size: f.size, blocks: map[int64]entry{}}
		for i, e := range f.blocks {
			s.blocks[i] = e
			b.meter.add("freeze", e.route, Counts{Metadata: 1})
		}
		r.manifest[n] = s
		b.meter.add("freeze", "metadata", Counts{Metadata: 1})
		if failAfter > 0 && len(r.manifest) >= failAfter {
			return fail()
		}
	}
	c.result = r
	return nil
}
func (r *root) check(build string, m *Meter, phase string) error {
	if r == nil || !r.sealed || r.build != build || r.manifest == nil {
		return errors.New("unsealed/identity")
	}
	if len(r.files) != len(r.manifest) || len(r.dirs) != len(r.dirManifest) {
		return errors.New("inventory mismatch")
	}
	for d := range r.dirManifest {
		if !r.dirs[d] {
			return errors.New("directory mismatch")
		}
		m.add(phase, "metadata", Counts{Metadata: 1})
	}
	for n, s := range r.manifest {
		f := r.files[n]
		if f != s.file || f.size != s.size || len(f.blocks) != len(s.blocks) {
			return errors.New("file mismatch")
		}
		for i, e := range s.blocks {
			if e.block == nil || e.valid < 0 || e.valid > BlockSize || i < 0 || i >= (f.size/BlockSize+min(f.size%BlockSize, 1)) || f.blocks[i] != e {
				return errors.New("block mismatch")
			}
			m.add(phase, e.route, Counts{Metadata: 1})
		}
		m.add(phase, "metadata", Counts{Metadata: 1})
	}
	return nil
}

type Owner struct {
	mu    sync.RWMutex
	r     *root
	meter *Meter
}

func (c *Capture) Acquire(build string, m *Meter) (*Owner, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.abandoned || c.taken || c.result == nil || c.result != c.expected || c.result.key != c.key {
		return nil, errors.New("capture substitution/state")
	}
	if e := c.result.check(build, m, "acquire"); e != nil {
		return nil, e
	}
	o := &Owner{r: c.result, meter: m}
	c.result = nil
	c.expected = nil
	c.taken = true
	return o, nil
}
func (o *Owner) Close() { o.mu.Lock(); defer o.mu.Unlock(); o.r = nil }
func (o *Owner) ReadAt(name string, p []byte, off int64) (int, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	if o.r == nil {
		return 0, errors.New("closed owner")
	}
	f := o.r.files[name]
	if f == nil {
		return 0, errors.New("missing file")
	}
	return readFile(f, p, off, o.meter, "application-read")
}
func (o *Owner) Fork(build string) (*Builder, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	if e := o.r.check(build, o.meter, "fork"); e != nil {
		return nil, e
	}
	b := New(build, o.meter)
	for d := range o.r.dirs {
		b.r.dirs[d] = true
	}
	for n, f := range o.r.files {
		nf := &file{size: f.size, blocks: map[int64]entry{}}
		for i, e := range f.blocks {
			e.writable = false
			e.route = "inherited"
			nf.blocks[i] = e
			o.meter.add("fork", "inherited", Counts{Metadata: 1})
		}
		b.r.files[n] = nf
	}
	return b, nil
}

// VerifyContents is a strict ownership-layer oracle/adapter, never called by Acquire.
// It intentionally rereads payload. Its expected values must originate elsewhere.
func (o *Owner) VerifyContents(build string, expected map[string]string) error {
	return o.verifyContents(build, expected, "strict")
}
func (o *Owner) verifyContents(build string, expected map[string]string, phase string) error {
	o.mu.RLock()
	defer o.mu.RUnlock()
	if e := o.r.check(build, o.meter, phase); e != nil {
		return e
	}
	if len(expected) != len(o.r.files) {
		return errors.New("strict inventory")
	}
	for n, f := range o.r.files {
		p := make([]byte, f.size)
		if _, e := readFile(f, p, 0, o.meter, phase); e != nil && e != io.EOF {
			return e
		}
		if o.meter.hash(phase, "content", p) != expected[n] {
			return errors.New("strict content mismatch")
		}
	}
	return nil
}

// Transfer mirrors the existing version-1 manifest shape; it is a model of
// serialization, not a replacement for the production path/FD importer.
type TransferEntry struct {
	Kind   string `json:"kind"`
	Bytes  *int64 `json:"bytes,omitempty"`
	SHA256 string `json:"sha256,omitempty"`
}
type Transfer struct {
	Format  string                   `json:"format"`
	Version int                      `json:"version"`
	WASM    string                   `json:"wasm_sha256"`
	Storage string                   `json:"source_storage"`
	Entries map[string]TransferEntry `json:"entries"`
	Data    map[string][]byte        `json:"-"`
}

func (o *Owner) Export() (*Transfer, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	if o.r == nil {
		return nil, errors.New("closed")
	}
	t := &Transfer{Format: "mariamem-cold-snapshot", Version: 1, WASM: o.r.build, Storage: "memory", Entries: map[string]TransferEntry{}, Data: map[string][]byte{}}
	for d := range o.r.dirs {
		t.Entries[d] = TransferEntry{Kind: "directory"}
	}
	names := make([]string, 0, len(o.r.files))
	for n := range o.r.files {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, n := range names {
		f := o.r.files[n]
		p := make([]byte, f.size)
		if _, e := readFile(f, p, 0, o.meter, "handoff-send"); e != nil && e != io.EOF {
			return nil, e
		}
		size := f.size
		t.Entries[n] = TransferEntry{Kind: "file", Bytes: &size, SHA256: o.meter.hash("handoff-send", "handoff", p)}
		t.Data[n] = p
	}
	return t, nil
}
func Import(t *Transfer, build string, m *Meter) (*Owner, error) {
	if t.Format != "mariamem-cold-snapshot" || t.Version != 1 || t.Storage != "memory" || t.WASM != build {
		return nil, errors.New("transfer identity")
	}
	if t.Entries["."].Kind != "directory" {
		return nil, errors.New("missing root")
	}
	b := New(build, m)
	b.writePhase = "handoff-copy"
	expected := map[string]string{}
	for n, e := range t.Entries {
		if n == "." {
			continue
		}
		if !validName(n) {
			return nil, errors.New("invalid transfer path")
		}
		if e.Kind == "directory" {
			b.r.dirs[n] = true
			continue
		}
		if e.Kind != "file" || e.Bytes == nil || *e.Bytes != int64(len(t.Data[n])) || len(e.SHA256) != 64 {
			return nil, errors.New("transfer metadata")
		}
		if m.hash("handoff-receive", "handoff", t.Data[n]) != e.SHA256 {
			return nil, errors.New("transfer corruption")
		}
		h, err := b.Open(n)
		if err != nil {
			return nil, err
		}
		if err = h.WriteAt(t.Data[n], 0); err != nil {
			return nil, err
		}
		h.Close()
		expected[n] = e.SHA256
	}
	if len(expected) != len(t.Data) {
		return nil, errors.New("extra data")
	}
	c, _ := b.Request()
	if e := b.Freeze(c, -1); e != nil {
		return nil, e
	}
	o, e := c.Acquire(build, m)
	if e != nil {
		return nil, e
	}
	if e = o.verifyContents(build, expected, "handoff-target-verify"); e != nil {
		o.Close()
		return nil, e
	}
	return o, nil
}

// ImportMapped copies borrowed mapping bytes into owned heap, then compares the
// target with an independently supplied digest before the mapping may be unmapped.
func ImportMapped(p []byte, expected, build string, m *Meter) (*Owner, error) {
	if m.hash("mapped-source", "mapped", p) != expected {
		return nil, errors.New("mapped source mismatch")
	}
	b := New(build, m)
	b.writePhase = "mapped-copy"
	h, _ := b.Open("mapped")
	if e := h.WriteAt(p, 0); e != nil {
		return nil, e
	}
	h.Close()
	c, _ := b.Request()
	if e := b.Freeze(c, -1); e != nil {
		return nil, e
	}
	o, e := c.Acquire(build, m)
	if e != nil {
		return nil, e
	}
	if e = o.verifyContents(build, map[string]string{"mapped": expected}, "mapped-target-verify"); e != nil {
		o.Close()
		return nil, e
	}
	return o, nil
}
