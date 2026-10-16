package base

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"os"
	"path"
	"sort"

	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/timing"
)

// FreezeHeap runs only after root and ALL workers have joined. It permanently
// seals producer blocks before transferring bytes, so no mutable alias survives.
func (fs *MemFS) FreezeHeap(build string) (*prepared.Heap, error) {
	return fs.freezeHeap(build, nil)
}

// Per-call failure injection is confined to package tests; no environment or
// production global can corrupt a sibling or an already immutable ancestor.
func (fs *MemFS) freezeHeap(build string, beforeVerify func(*prepared.Heap) (*prepared.Heap, error)) (*prepared.Heap, error) {
	ctx, finish := timing.Begin(context.Background(), "snapshot_freeze")
	defer finish()
	fs.mu.Lock()
	defer fs.mu.Unlock()
	root, e := fs.lookup("mariadb")
	if e != nil {
		return nil, e
	}
	dirs := []string{}
	files := map[string]*prepared.HeapFile{}
	buf := make([]byte, prepared.BlockSize)
	var walk func(*memNode, string) error
	walk = func(n *memNode, name string) error {
		if n.dir {
			dirs = append(dirs, name)
			names := make([]string, 0, len(n.children))
			for k := range n.children {
				names = append(names, k)
			}
			sort.Strings(names)
			for _, k := range names {
				if e := walk(n.children[k], path.Join(name, k)); e != nil {
					return e
				}
			}
			return nil
		}
		d := n.blocks
		if d == nil || d.sealed {
			return nilStorageError()
		}
		d.sealed = true
		blocks := make([]prepared.Block, d.size/prepared.BlockSize+min(d.size%prepared.BlockSize, 1))
		sum := sha256.New()
		for off := int64(0); off < d.size; off += prepared.BlockSize {
			count := min(int64(len(buf)), d.size-off)
			if _, e := d.readAt(buf[:count], off); e != nil {
				return e
			}
			sum.Write(buf[:count])
			i := off / prepared.BlockSize
			if b := d.dirty[i]; b != nil {
				blocks[i], e = prepared.TakeBlock(b, int(count))
			} else if off < d.inheritedLimit && d.base != nil {
				b := make([]byte, prepared.BlockSize)
				d.original(b, off)
				blocks[i], e = prepared.TakeBlock(b, int(count))
			} else if off < d.inheritedLimit && i < int64(len(d.inherited)) {
				blocks[i] = d.inherited[i].Limit(int(min(count, d.inheritedLimit-off)))
			}
			if e != nil {
				return e
			}
		}
		f, e := prepared.NewHeapFile(d.size, blocks, hex.EncodeToString(sum.Sum(nil)))
		if e != nil {
			return e
		}
		files[name] = f
		// The original FS retains read-only descriptors only; no dirty block writer.
		d.dirty = nil
		d.base = nil
		d.inherited = f.Blocks()
		d.inheritedLimit = d.size
		return nil
	}
	if e = walk(root, "."); e != nil {
		return nil, e
	}
	timing.Mark(ctx, "source_inventory_hashed")
	h, e := prepared.NewHeap(build, dirs, files)
	if e != nil {
		return nil, e
	}
	if beforeVerify != nil {
		if h, e = beforeVerify(h); e != nil {
			return nil, e
		}
	}
	// Second full content pass checks the exact transferred target descriptors.
	if e = h.Verify(build); e != nil {
		return nil, e
	}
	timing.Mark(ctx, "target_verified")
	return h, nil
}
func nilStorageError() error { return errors.New("snapshot requires unsealed block storage") }

func mapHeap(fs *MemFS, h *prepared.Heap, prefix string) (*PreparedFiles, error) {
	if !fs.blockStorage {
		return nil, errors.New("heap requires block storage")
	}
	if e := h.Check(h.Build()); e != nil {
		return nil, e
	}
	for _, n := range h.Dirs() {
		if e := fs.MkdirAll(path.Join(prefix, n), 0700); e != nil {
			return nil, e
		}
	}
	for _, n := range h.Names() {
		f := h.File(n)
		dst := path.Join(prefix, n)
		fd, e := fs.OpenFile(dst, os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
		if e != nil {
			return nil, e
		}
		if e = fd.Close(); e != nil {
			return nil, e
		}
		fs.mu.Lock()
		node, e := fs.lookup(dst)
		if e == nil {
			node.blocks.size = f.Size()
			node.blocks.inheritedLimit = f.Size()
			node.blocks.inherited = f.Blocks()
		}
		fs.mu.Unlock()
		if e != nil {
			return nil, e
		}
	}
	return &PreparedFiles{}, nil
}

// Keep io.ReaderAt's end semantics visible to the storage reference tests.
var _ io.ReaderAt = (*prepared.HeapFile)(nil)
