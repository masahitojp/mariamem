package base

import (
	"os"

	"github.com/masahitojp/mariamem/internal/prepared"
)

// Storage bytes and immutable ownership live in prepared; MemFS retains its lock/FD semantics.
type blockStorage struct{ file *prepared.FileStore }

func newBlockStorage(source ...*prepared.RootSource) *blockStorage {
	s := prepared.NewRootSource(false)
	if len(source) > 0 && source[0] != nil {
		s = source[0]
	}
	return &blockStorage{prepared.NewFileStore(s)}
}
func (d *blockStorage) readAt(p []byte, off int64) (int, error)  { return d.file.ReadAt(p, off) }
func (d *blockStorage) writeAt(p []byte, off int64) (int, error) { return d.file.WriteAt(p, off) }
func (d *blockStorage) resize(n int64) error                     { return d.file.Resize(n) }
func (n *memNode) storageSize() int64 {
	if n.blocks != nil {
		return n.blocks.file.Size()
	}
	return int64(len(n.data))
}
func NewBlockMemFS() *MemFS {
	fs := NewMemFS()
	fs.blockStorage = true
	fs.rootSource = prepared.NewRootSource(os.Getenv("MARIAMEM_TIMING_DIR") != "")
	return fs
}
func (fs *MemFS) RootSource() *prepared.RootSource { return fs.rootSource }
func (fs *MemFS) enroll(n *memNode) {
	if fs.blockStorage && !n.dir {
		n.blocks = newBlockStorage(fs.rootSource)
	}
}
func (fs *MemFS) installMappedStorage(n *memNode, data []byte) {
	if !fs.blockStorage {
		n.data = data
		return
	}
	n.blocks = newBlockStorage(fs.rootSource)
	// The caller holds fs.mu and this store is fresh, empty and unsealed.
	// BorrowMapping rejects only nonempty/sealed stores, so failure here means
	// an internal invariant was broken. External open/stat/mmap errors are
	// returned by MapPreparedFiles before installation; this helper does no I/O.
	if e := n.blocks.file.BorrowMapping(data); e != nil {
		panic(e)
	}
	n.data = nil
}
