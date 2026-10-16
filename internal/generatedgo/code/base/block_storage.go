package base

import (
	"errors"
	"io"
	"syscall"

	"github.com/masahitojp/mariamem/internal/prepared"
)

// blockStorage is mutable only under its MemFS lock. Ancestor block bytes are
// immutable; the first child write copies at most one block. base is a borrowed
// read-only mapping owned by this instance, and never escapes into a Heap.
type blockStorage struct {
	size, inheritedLimit int64
	inherited            []prepared.Block
	base                 []byte
	dirty                map[int64][]byte
	sealed               bool
}

func newBlockStorage() *blockStorage { return &blockStorage{dirty: map[int64][]byte{}} }
func (d *blockStorage) original(dst []byte, off int64) {
	clear(dst)
	end := min(off+int64(len(dst)), d.inheritedLimit)
	if end <= off {
		return
	}
	if d.base != nil {
		copy(dst, d.base[off:end])
		return
	}
	if off/int64(prepared.BlockSize) < int64(len(d.inherited)) {
		d.inherited[off/prepared.BlockSize].ReadAt(dst[:end-off], int(off%prepared.BlockSize))
	}
}
func (d *blockStorage) readAt(dst []byte, off int64) (int, error) {
	if off < 0 {
		return 0, syscall.EINVAL
	}
	if len(dst) == 0 {
		return 0, nil
	}
	if off >= d.size {
		return 0, io.EOF
	}
	count := min(int64(len(dst)), d.size-off)
	var done int64
	for done < count {
		at := off + done
		index := at / prepared.BlockSize
		in := at % prepared.BlockSize
		n := min(count-done, int64(prepared.BlockSize)-in)
		out := dst[done : done+n]
		if b := d.dirty[index]; b != nil {
			copy(out, b[in:in+n])
		} else {
			d.original(out, at)
		}
		done += n
	}
	if done < int64(len(dst)) {
		return int(done), io.EOF
	}
	return int(done), nil
}
func (d *blockStorage) writeAt(src []byte, off int64) (int, error) {
	if d.sealed {
		return 0, errors.New("snapshot storage is sealed")
	}
	if off < 0 || off > int64(^uint(0)>>1)-int64(len(src)) {
		return 0, syscall.EFBIG
	}
	if len(src) == 0 {
		return 0, nil
	}
	var done int64
	for done < int64(len(src)) {
		at := off + done
		index := at / prepared.BlockSize
		in := at % prepared.BlockSize
		n := min(int64(len(src))-done, int64(prepared.BlockSize)-in)
		b := d.dirty[index]
		if b == nil {
			b = make([]byte, prepared.BlockSize)
			d.original(b, index*prepared.BlockSize)
			d.dirty[index] = b
		}
		copy(b[in:in+n], src[done:done+n])
		done += n
	}
	d.size = max(d.size, off+done)
	return int(done), nil
}
func (d *blockStorage) resize(size int64) error {
	if d.sealed {
		return errors.New("snapshot storage is sealed")
	}
	if size < 0 || size > int64(^uint(0)>>1) {
		return syscall.EINVAL
	}
	if size < d.size {
		for i := range d.dirty {
			if i*prepared.BlockSize >= size {
				delete(d.dirty, i)
			}
		}
		if size%prepared.BlockSize != 0 {
			if b := d.dirty[size/prepared.BlockSize]; b != nil {
				clear(b[size%prepared.BlockSize:])
			}
		}
		d.inheritedLimit = min(d.inheritedLimit, size)
		keep := (d.inheritedLimit / prepared.BlockSize) + min(d.inheritedLimit%prepared.BlockSize, 1)
		if keep < int64(len(d.inherited)) {
			clear(d.inherited[keep:])
			d.inherited = d.inherited[:keep]
		}
	}
	d.size = size
	return nil
}
func (n *memNode) storageSize() int64 {
	if n.blocks != nil {
		return n.blocks.size
	}
	return int64(len(n.data))
}

// NewBlockMemFS retains the reference MemFS metadata/locking behavior and uses
// block storage for regular files. It is independent of OS page CoW support.
func NewBlockMemFS() *MemFS { fs := NewMemFS(); fs.blockStorage = true; return fs }
func (fs *MemFS) enroll(n *memNode) {
	if fs.blockStorage && !n.dir {
		n.blocks = newBlockStorage()
	}
}

func (fs *MemFS) installMappedStorage(n *memNode, data []byte) {
	if !fs.blockStorage {
		n.data = data
		return
	}
	n.blocks = newBlockStorage()
	n.blocks.base = data
	n.blocks.size = int64(len(data))
	n.blocks.inheritedLimit = int64(len(data))
	n.data = nil
}
