package base

import (
	"errors"
	"os"
	"path/filepath"
	"syscall"

	"github.com/masahitojp/mariamem/internal/prepared"
)

// MapPreparedHandles restores the sealed root or verified backing pinned by its
// owner. Root and borrowed FD restores do not rescan payload. Strict Heap import
// copies and verifies its content before entering the ordinary root path.
func MapPreparedHandles(fsys *MemFS, entries []prepared.Entry, prefix string) (_ *PreparedFiles, err error) {
	if len(entries) == 1 && entries[0].Root != nil {
		return mapRoot(fsys, entries[0].Root, prefix)
	}
	if len(entries) == 1 && entries[0].Heap != nil {
		return mapHeap(fsys, entries[0].Heap, prefix)
	}
	p := &PreparedFiles{}
	defer func() {
		if err != nil {
			err = errors.Join(err, p.Close())
		}
	}()
	for _, entry := range entries {
		dest := filepath.ToSlash(filepath.Join(prefix, entry.Name))
		if entry.Directory {
			if err = fsys.MkdirAll(dest, 0700); err != nil {
				return nil, err
			}
			continue
		}
		if entry.FD < 0 || entry.Size < 0 || int64(int(entry.Size)) != entry.Size {
			return nil, errors.New("invalid prepared handle")
		}
		var data []byte
		if entry.Size > 0 {
			data, err = syscall.Mmap(entry.FD, 0, int(entry.Size), preparedProtection(fsys), syscall.MAP_PRIVATE)
			if err != nil {
				return nil, err
			}
			p.mappings = append(p.mappings, data)
		}
		opened, e := fsys.OpenFile(dest, os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
		if e != nil {
			return nil, e
		}
		opened.Close()
		fsys.mu.Lock()
		node, e := fsys.lookup(dest)
		if e == nil {
			if fsys.blockStorage {
				node.blocks = newBlockStorage(fsys.rootSource)
				e = node.blocks.file.BorrowMapping(data)
			} else {
				node.data = data
			}
		}
		fsys.mu.Unlock()
		if e != nil {
			return nil, e
		}
	}
	return p, nil
}

func preparedProtection(fs *MemFS) int {
	if fs.blockStorage {
		return syscall.PROT_READ
	}
	return syscall.PROT_READ | syscall.PROT_WRITE
}
