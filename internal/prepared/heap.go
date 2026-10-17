package prepared

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"path"
	"sort"
	"sync"
)

const BlockSize = 16 * 1024

// Block is immutable after transfer. No method exposes its bytes to a reader.
// valid masks truncated tails without copying an ancestor's block.
type Block struct {
	data  []byte
	valid int
}

// TakeBlock transfers a private block after its producer has stopped writing.
// Callers must discard every mutable alias. A zero Block denotes implicit zeros.
func TakeBlock(data []byte, valid int) (Block, error) {
	if len(data) != BlockSize || valid < 0 || valid > BlockSize {
		return Block{}, errors.New("invalid snapshot block")
	}
	return Block{data: data, valid: valid}, nil
}
func (b Block) Limit(n int) Block {
	if n < b.valid {
		b.valid = max(0, n)
	}
	return b
}
func (b Block) ReadAt(dst []byte, off int) {
	clear(dst)
	if off < b.valid {
		copy(dst, b.data[off:min(b.valid, off+len(dst))])
	}
}

// HeapFile owns only immutable block descriptors, never producer storage objects.
type HeapFile struct {
	size   int64
	blocks []Block
	digest string
}

func NewHeapFile(size int64, blocks []Block, digest string) (*HeapFile, error) {
	if size < 0 || size > int64(^uint(0)>>1) || int64(len(blocks)) != (size/BlockSize+min(size%BlockSize, 1)) {
		return nil, errors.New("invalid snapshot file layout")
	}
	h, e := hex.DecodeString(digest)
	if e != nil || len(h) != sha256.Size {
		return nil, errors.New("invalid snapshot file hash")
	}
	return &HeapFile{size: size, blocks: append([]Block(nil), blocks...), digest: digest}, nil
}
func (f *HeapFile) Size() int64     { return f.size }
func (f *HeapFile) Digest() string  { return f.digest }
func (f *HeapFile) Blocks() []Block { return append([]Block(nil), f.blocks...) }
func (f *HeapFile) ReadAt(dst []byte, off int64) (int, error) {
	if off < 0 {
		return 0, errors.New("negative snapshot offset")
	}
	if len(dst) == 0 {
		return 0, nil
	}
	if off >= f.size {
		return 0, io.EOF
	}
	count := min(int64(len(dst)), f.size-off)
	var done int64
	for done < count {
		at := off + done
		in := int(at % BlockSize)
		n := min(count-done, int64(BlockSize-in))
		f.blocks[at/BlockSize].ReadAt(dst[done:done+n], in)
		done += n
	}
	if done < int64(len(dst)) {
		return int(done), io.EOF
	}
	return int(done), nil
}

// Heap is immutable, including metadata. A borrower can retain it independently
// of the Snapshot handle; blocks remain reachable until the final child closes.
type Heap struct {
	build string
	dirs  []string
	files map[string]*HeapFile
}

func NewHeap(build string, dirs []string, files map[string]*HeapFile) (*Heap, error) {
	h := &Heap{build: build, dirs: append([]string(nil), dirs...), files: make(map[string]*HeapFile, len(files))}
	for n, f := range files {
		h.files[n] = f
	}
	if e := h.Check(build); e != nil {
		return nil, e
	}
	return h, nil
}
func (h *Heap) Build() string  { return h.build }
func (h *Heap) Dirs() []string { return append([]string(nil), h.dirs...) }
func (h *Heap) Names() []string {
	a := make([]string, 0, len(h.files))
	for n := range h.files {
		a = append(a, n)
	}
	sort.Strings(a)
	return a
}
func (h *Heap) File(n string) *HeapFile { return h.files[n] }
func (h *Heap) Check(build string) error {
	if h == nil || h.build != build {
		return errors.New("snapshot guest identity mismatch")
	}
	dirs := map[string]bool{}
	valid := func(n string) bool {
		return n != "" && !path.IsAbs(n) && path.Clean(n) == n && n != ".." && !(len(n) >= 3 && n[:3] == "../")
	}
	for _, n := range h.dirs {
		if !valid(n) || dirs[n] {
			return errors.New("invalid snapshot directory")
		}
		dirs[n] = true
	}
	if !dirs["."] {
		return errors.New("missing snapshot root")
	}
	for _, n := range h.dirs {
		if n != "." && !dirs[path.Dir(n)] {
			return errors.New("missing snapshot directory parent")
		}
	}
	for n, f := range h.files {
		if !valid(n) || dirs[n] || !dirs[path.Dir(n)] || f == nil {
			return errors.New("invalid snapshot file")
		}
	}
	return nil
}
func (h *Heap) Verify(build string) error {
	if e := h.Check(build); e != nil {
		return e
	}
	buf := make([]byte, BlockSize)
	for _, n := range h.Names() {
		f := h.files[n]
		sum := sha256.New()
		for off := int64(0); off < f.size; off += BlockSize {
			count := min(int64(len(buf)), f.size-off)
			if _, e := f.ReadAt(buf[:count], off); e != nil {
				return e
			}
			sum.Write(buf[:count])
		}
		if hex.EncodeToString(sum.Sum(nil)) != f.digest {
			return fmt.Errorf("snapshot content mismatch: %s", n)
		}
	}
	return nil
}

// Capture is per execution, with no global registry or environment switches.
// The result is read only after instance completion. Requests precede Shutdown.
type Capture struct {
	mu                     sync.Mutex
	requested              bool
	abandoned              bool
	result                 *Heap
	source                 *RootSource
	build                  string
	native, expectedNative *Root
	taken                  bool
}

func (c *Capture) Request()        { c.mu.Lock(); defer c.mu.Unlock(); c.requested = true }
func (c *Capture) Requested() bool { c.mu.Lock(); defer c.mu.Unlock(); return c.requested }
func (c *Capture) Complete(h *Heap) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if !c.abandoned {
		c.result = h
	}
}
func (c *Capture) Result() *Heap { c.mu.Lock(); defer c.mu.Unlock(); return c.result }

// TakeResult removes the producer transport's reference after ownership moves.
func (c *Capture) TakeResult() *Heap {
	c.mu.Lock()
	defer c.mu.Unlock()
	h := c.result
	c.result = nil
	return h
}

func (c *Capture) Discard() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.abandoned = true
	c.result = nil
	c.native = nil
	c.expectedNative = nil
	c.source = nil
}
