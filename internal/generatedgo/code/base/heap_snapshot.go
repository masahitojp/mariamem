package base

import (
	"context"
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
		if d == nil || d.file.Sealed() {
			return nilStorageError()
		}
		frozen, e := d.file.Seal()
		if e != nil {
			return e
		}
		f, e := frozen.LegacyFile()
		if e != nil {
			return e
		}
		files[name] = f
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
			var store *prepared.FileStore
			store, e = prepared.StoreFromHeap(fs.rootSource, f)
			if e == nil {
				node.blocks = &blockStorage{file: store}
			}
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

// FreezeRoot runs after joined guest completion, under the same namespace lock as every mutation.
func (fs *MemFS) FreezeRoot(build string, capture *prepared.Capture) error {
	ctx, finish := timing.Begin(context.Background(), "snapshot_freeze")
	defer finish()
	fs.mu.Lock()
	defer fs.mu.Unlock()
	node, e := fs.lookup("mariadb")
	if e != nil {
		return e
	}
	dirs := []string{}
	files := map[string]*prepared.FrozenFile{}
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
		if n.blocks == nil {
			return nilStorageError()
		}
		f, e := n.blocks.file.Seal()
		if e != nil {
			return e
		}
		files[name] = f
		return nil
	}
	if e = walk(node, "."); e != nil {
		return e
	}
	timing.Mark(ctx, "root_files_sealed")
	e = capture.CompleteRoot(fs.rootSource, build, dirs, files)
	timing.Mark(ctx, "root_capture_completed")
	return e
}
func mapRoot(fs *MemFS, r *prepared.Root, prefix string) (*PreparedFiles, error) {
	if !fs.blockStorage {
		return nil, errors.New("root requires block storage")
	}
	if e := r.Check(r.Build()); e != nil {
		return nil, e
	}
	for _, n := range r.Dirs() {
		if e := fs.MkdirAll(path.Join(prefix, n), 0700); e != nil {
			return nil, e
		}
	}
	for _, n := range r.Names() {
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
			node.blocks = &blockStorage{file: r.File(n).Fork(fs.rootSource)}
		}
		fs.mu.Unlock()
		if e != nil {
			return nil, e
		}
	}
	return &PreparedFiles{}, nil
}
