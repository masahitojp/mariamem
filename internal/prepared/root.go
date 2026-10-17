package prepared

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"sort"
	"sync"
	"syscall"
)

// RootSource is per MemFS. It contains no filesystem, runtime or parent root.
// Its nonzero size makes distinct live source identities distinct pointers.
type RootSource struct {
	marker byte
	meter  *RootMeter
}

func NewRootSource(observe bool) *RootSource {
	s := &RootSource{marker: 1}
	if observe {
		s.meter = &RootMeter{counts: map[string]RootCounts{}}
	}
	return s
}

type RootCounts struct{ Read, Copy, Hash, Zero, Metadata int64 }
type RootMeter struct {
	mu     sync.Mutex
	counts map[string]RootCounts
}

func (s *RootSource) work(k string, read, copy, hash, zero, meta int64) {
	if s == nil || s.meter == nil {
		return
	}
	m := s.meter
	m.mu.Lock()
	defer m.mu.Unlock()
	v := m.counts[k]
	v.Read += read
	v.Copy += copy
	v.Hash += hash
	v.Zero += zero
	v.Metadata += meta
	m.counts[k] = v
}
func (s *RootSource) Counts() map[string]RootCounts {
	out := map[string]RootCounts{}
	if s == nil || s.meter == nil {
		return out
	}
	s.meter.mu.Lock()
	defer s.meter.mu.Unlock()
	for k, v := range s.meter.counts {
		out[k] = v
	}
	return out
}

type rootBlock struct {
	block Block
	route string
}
type rootFileData struct {
	size    int64
	blocks  map[int64]rootBlock
	mapping []byte
	limit   int64
	sealed  bool
}
type FileStore struct {
	mu      sync.Mutex
	source  *RootSource
	data    *rootFileData
	private map[int64]bool
}
type FrozenFile struct {
	source *RootSource
	data   *rootFileData
}

func NewFileStore(source *RootSource) *FileStore {
	return &FileStore{source: source, data: &rootFileData{blocks: map[int64]rootBlock{}}, private: map[int64]bool{}}
}
func (s *FileStore) Size() int64  { s.mu.Lock(); defer s.mu.Unlock(); return s.data.size }
func (s *FileStore) Sealed() bool { s.mu.Lock(); defer s.mu.Unlock(); return s.data.sealed }
func (s *FileStore) BorrowMapping(p []byte) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.data.sealed || len(s.data.blocks) > 0 || s.data.size != 0 {
		return errors.New("nonempty mapped store")
	}
	s.data.mapping = p
	s.data.size = int64(len(p))
	s.data.limit = int64(len(p))
	return nil
}
func rootRead(d *rootFileData, p []byte, off int64, source *RootSource, phase string) (int, error) {
	if off < 0 {
		return 0, syscall.EINVAL
	}
	if len(p) == 0 {
		return 0, nil
	}
	if off >= d.size {
		return 0, io.EOF
	}
	count := int(min(int64(len(p)), d.size-off))
	for done := 0; done < count; {
		at := off + int64(done)
		in := int(at % BlockSize)
		n := min(count-done, BlockSize-in)
		dst := p[done : done+n]
		e, ok := d.blocks[at/BlockSize]
		if ok {
			e.block.ReadAt(dst, in)
			nr := max(0, min(n, e.block.valid-in))
			source.work(phase+"/"+e.route, int64(nr), int64(nr), 0, int64(n-nr), 0)
		} else {
			clear(dst)
			nr := int(max(int64(0), min(int64(n), d.limit-at)))
			if nr > 0 && d.mapping != nil {
				copy(dst[:nr], d.mapping[at:at+int64(nr)])
			} else {
				nr = 0
			}
			route := "zero"
			if nr > 0 {
				route = "mapped"
			}
			source.work(phase+"/"+route, int64(nr), int64(nr), 0, int64(n-nr), 0)
		}
		done += n
	}
	if count < len(p) {
		return count, io.EOF
	}
	return count, nil
}
func (s *FileStore) ReadAt(p []byte, off int64) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return rootRead(s.data, p, off, s.source, "io-read")
}
func (s *FileStore) WriteAt(p []byte, off int64) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	d := s.data
	if d.sealed {
		return 0, errors.New("snapshot storage is sealed")
	}
	if off < 0 || off > int64(^uint(0)>>1)-int64(len(p)) {
		return 0, syscall.EFBIG
	}
	if len(p) == 0 {
		return 0, nil
	}
	for done := 0; done < len(p); {
		at := off + int64(done)
		i := at / BlockSize
		in := int(at % BlockSize)
		n := min(len(p)-done, BlockSize-in)
		e := d.blocks[i]
		if !s.private[i] {
			b := make([]byte, BlockSize)
			if _, err := rootRead(d, b, i*BlockSize, s.source, "cow"); err != nil && err != io.EOF {
				return done, err
			}
			valid := int(min(int64(BlockSize), max(int64(0), d.size-i*BlockSize)))
			e = rootBlock{Block{data: b, valid: valid}, "dirty"}
			s.private[i] = true
		}
		if in > e.block.valid {
			clear(e.block.data[e.block.valid:in])
			s.source.work("write/dirty", 0, 0, 0, int64(in-e.block.valid), 0)
		}
		copy(e.block.data[in:in+n], p[done:done+n])
		e.block.valid = max(e.block.valid, in+n)
		e.route = "dirty"
		d.blocks[i] = e
		s.source.work("write/dirty", int64(n), int64(n), 0, 0, 0)
		done += n
	}
	d.size = max(d.size, off+int64(len(p)))
	return len(p), nil
}
func (s *FileStore) Resize(n int64) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	d := s.data
	if d.sealed {
		return errors.New("snapshot storage is sealed")
	}
	if n < 0 || n > int64(^uint(0)>>1) {
		return syscall.EINVAL
	}
	if n < d.size {
		for i, e := range d.blocks {
			if i >= n/BlockSize && (i > n/BlockSize || n%BlockSize == 0) {
				delete(d.blocks, i)
				delete(s.private, i)
			} else if i == n/BlockSize {
				e.block = e.block.Limit(int(n % BlockSize))
				d.blocks[i] = e
			}
		}
		d.limit = min(d.limit, n)
	}
	d.size = n
	return nil
}
func fileDigest(d *rootFileData, s *RootSource, phase string) (string, error) {
	h := sha256.New()
	buf := make([]byte, BlockSize)
	for off := int64(0); off < d.size; off += BlockSize {
		n := int(min(int64(BlockSize), d.size-off))
		if _, e := rootRead(d, buf[:n], off, s, phase); e != nil {
			return "", e
		}
		h.Write(buf[:n])
		s.work(phase+"/hash", int64(n), 0, int64(n), 0, 0)
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
func (s *FileStore) Seal() (*FrozenFile, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	d := s.data
	if d.sealed {
		return nil, errors.New("already sealed")
	}
	// Borrowed mapping cannot escape its instance. Independently compare the
	// original logical content with the materialized heap target on this route.
	if d.mapping != nil {
		before, e := fileDigest(d, s.source, "mapped-source")
		if e != nil {
			return nil, e
		}
		for off := int64(0); off < min(d.limit, d.size); off += BlockSize {
			if _, ok := d.blocks[off/BlockSize]; ok {
				continue
			}
			p := make([]byte, BlockSize)
			n := int(min(int64(BlockSize), d.size-off))
			if _, e = rootRead(d, p[:n], off, s.source, "mapped-copy"); e != nil {
				return nil, e
			}
			d.blocks[off/BlockSize] = rootBlock{Block{p, n}, "mapped"}
		}
		d.mapping = nil
		d.limit = 0
		after, e := fileDigest(d, s.source, "mapped-target")
		if e != nil {
			return nil, e
		}
		if before != after {
			return nil, errors.New("mapped target mismatch")
		}
	}
	if s.source.meter != nil {
		if len(d.blocks) == 0 {
			s.source.work("freeze/zero", 0, 0, 0, 0, 1)
		}
		for _, b := range d.blocks {
			s.source.work("freeze/"+b.route, 0, 0, 0, 0, 1)
		}
	}
	d.sealed = true
	s.private = nil
	return &FrozenFile{source: s.source, data: d}, nil
}
func (f *FrozenFile) Size() int64 { return f.data.size }
func (f *FrozenFile) ReadAt(p []byte, off int64) (int, error) {
	return rootRead(f.data, p, off, f.source, "frozen-read")
}
func (f *FrozenFile) Fork(source *RootSource) *FileStore {
	s := NewFileStore(source)
	s.data.size = f.data.size
	for i, e := range f.data.blocks {
		e.route = "inherited"
		s.data.blocks[i] = e
		source.work("fork/metadata", 0, 0, 0, 0, 1)
	}
	return s
}

// LegacyFile is the explicit digest-bearing boundary, never called in heap capture.
func (f *FrozenFile) LegacyFile() (*HeapFile, error) {
	sum, e := fileDigest(f.data, f.source, "strict")
	if e != nil {
		return nil, e
	}
	blocks := make([]Block, f.Size()/BlockSize+min(f.Size()%BlockSize, 1))
	for i, e := range f.data.blocks {
		blocks[i] = e.block
	}
	return NewHeapFile(f.Size(), blocks, sum)
}
func StoreFromHeap(source *RootSource, f *HeapFile) *FileStore {
	s := NewFileStore(source)
	s.data.size = f.size
	for i, b := range f.blocks {
		if b.data != nil {
			s.data.blocks[int64(i)] = rootBlock{b, "inherited"}
		}
	}
	return s
}

// Root has no public constructor accepting a raw Heap or a verified flag.
// Capture is the only constructor, tied to a source bound before guest execution.
type rootStamp struct {
	file   *FrozenFile
	size   int64
	blocks map[int64]rootBlock
}
type Root struct {
	source   *RootSource
	build    string
	dirs     []string
	files    map[string]*FrozenFile
	stamps   map[string]rootStamp
	dirStamp map[string]bool
}

func (r *Root) Build() string  { return r.build }
func (r *Root) Dirs() []string { return append([]string(nil), r.dirs...) }
func (r *Root) Names() []string {
	a := make([]string, 0, len(r.files))
	for n := range r.files {
		a = append(a, n)
	}
	sort.Strings(a)
	return a
}
func (r *Root) File(n string) *FrozenFile     { return r.files[n] }
func (r *Root) Counts() map[string]RootCounts { return r.source.Counts() }
func (r *Root) Check(build string) error {
	if r == nil || r.build != build || r.source == nil {
		return errors.New("root guest identity mismatch")
	}
	// Reuse the exact existing namespace checks without payload or fake digests.
	if e := checkRootNames(r.dirs, r.files); e != nil {
		return e
	}
	if len(r.files) != len(r.stamps) || len(r.dirs) != len(r.dirStamp) {
		return errors.New("root inventory changed")
	}
	for _, n := range r.dirs {
		if !r.dirStamp[n] {
			return errors.New("root directories changed")
		}
	}
	for n, f := range r.files {
		stamp, ok := r.stamps[n]
		if !ok || f != stamp.file || f.data.size != stamp.size || len(f.data.blocks) != len(stamp.blocks) {
			return errors.New("root file changed")
		}
		for i, e := range f.data.blocks {
			old, ok := stamp.blocks[i]
			if !ok || e.block.valid != old.block.valid || len(e.block.data) != len(old.block.data) || len(e.block.data) == 0 || &e.block.data[0] != &old.block.data[0] {
				return errors.New("root block changed")
			}
		}
	}
	for _, f := range r.files {
		if f == nil || f.source != r.source || !f.data.sealed || f.data.mapping != nil {
			return errors.New("root file ownership mismatch")
		}
		for i, b := range f.data.blocks {
			if i < 0 || i >= f.Size()/BlockSize+min(f.Size()%BlockSize, 1) || b.block.valid < 0 || b.block.valid > BlockSize || len(b.block.data) != BlockSize {
				return errors.New("root block layout mismatch")
			}
			r.source.work("acquire/metadata", 0, 0, 0, 0, 1)
		}
	}
	return nil
}
func (c *Capture) BindRootSource(source *RootSource, build string) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if source == nil || build == "" || c.source != nil || c.abandoned {
		return errors.New("capture source already bound/invalid")
	}
	c.source = source
	c.build = build
	return nil
}
func (c *Capture) CompleteRoot(source *RootSource, build string, dirs []string, files map[string]*FrozenFile) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.abandoned || !c.requested || c.source != source || c.build != build || c.native != nil || c.taken {
		return errors.New("capture root/source/state mismatch")
	}
	r := &Root{source: source, build: build, dirs: append([]string(nil), dirs...), files: map[string]*FrozenFile{}, stamps: map[string]rootStamp{}, dirStamp: map[string]bool{}}
	for _, d := range dirs {
		r.dirStamp[d] = true
	}
	for n, f := range files {
		if f == nil {
			return errors.New("nil frozen file")
		}
		r.files[n] = f
		stamp := rootStamp{file: f, size: f.Size(), blocks: map[int64]rootBlock{}}
		for i, e := range f.data.blocks {
			stamp.blocks[i] = e
		}
		r.stamps[n] = stamp
	}
	if e := r.Check(build); e != nil {
		return e
	}
	c.native = r
	c.expectedNative = r
	return nil
}
func (c *Capture) TakeRoot(build string) (result *Root, err error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	defer func() {
		if err != nil {
			c.native = nil
			c.expectedNative = nil
			c.source = nil
			c.taken = true
		}
	}()
	if c.abandoned || c.taken || c.native == nil || c.native != c.expectedNative || c.native.source != c.source {
		return nil, errors.New("missing/substituted capture root")
	}
	if e := c.native.Check(build); e != nil {
		return nil, e
	}
	r := c.native
	c.native = nil
	c.expectedNative = nil
	c.source = nil
	c.taken = true
	return r, nil
}
