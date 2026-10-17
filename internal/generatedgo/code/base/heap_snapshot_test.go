package base

import (
	"bytes"
	"errors"
	"os"
	"testing"

	"github.com/masahitojp/mariamem/internal/prepared"
)

func TestHeapOwnershipAcrossGenerations(t *testing.T) {
	fs := NewBlockMemFS()
	fs.MkdirAll("mariadb", 0700)
	f, _ := fs.OpenFile("mariadb/data", os.O_CREATE|os.O_RDWR, 0600)
	original := bytes.Repeat([]byte{7}, 2*prepared.BlockSize+3)
	f.WriteAt(original, 0)
	f.Truncate(4 * prepared.BlockSize)
	image, e := fs.FreezeHeap("guest")
	if e != nil {
		t.Fatal(e)
	}
	if _, e = f.WriteAt([]byte{9}, 0); e == nil {
		t.Fatal("producer remains mutable")
	}
	for gen := 0; gen < 10; gen++ {
		child := NewBlockMemFS()
		if _, e = mapHeap(child, image, "mariadb"); e != nil {
			t.Fatal(e)
		}
		cf, _ := child.OpenFile("mariadb/data", os.O_RDWR, 0600)
		cf.WriteAt([]byte{byte(gen + 20)}, prepared.BlockSize-1)
		cf.Truncate(prepared.BlockSize + 1)
		cf.Truncate(4 * prepared.BlockSize)
		buf := make([]byte, 1)
		image.File("data").ReadAt(buf, prepared.BlockSize-1)
		if buf[0] != 7 && gen == 0 {
			t.Fatal("parent changed")
		}
		if e := image.Verify("guest"); e != nil {
			t.Fatal("child mutated parent", e)
		}
		next, e := child.FreezeHeap("guest")
		if e != nil {
			t.Fatal(e)
		}
		if e = next.Verify("guest"); e != nil {
			t.Fatal(e)
		}
		tail := make([]byte, 4*prepared.BlockSize-(prepared.BlockSize+1))
		next.File("data").ReadAt(tail, prepared.BlockSize+1)
		if !bytes.Equal(tail, make([]byte, len(tail))) {
			t.Fatal("ancestor tail leaked")
		}
		image = next
	}
}
func TestHeapFreezeFailureAndIdentityOracle(t *testing.T) {
	fs := NewBlockMemFS()
	fs.WriteFile("mariadb/f", []byte("abc"), 0600)
	_, e := fs.freezeHeap("guest", func(*prepared.Heap) (*prepared.Heap, error) { return nil, errors.New("injected freeze failure") })
	if e == nil {
		t.Fatal("failure hidden")
	}
	fs = NewBlockMemFS()
	fs.WriteFile("mariadb/f", []byte("abc"), 0600)
	h, e := fs.FreezeHeap("guest")
	if e != nil {
		t.Fatal(e)
	}
	if e = h.Verify("old guest"); e == nil {
		t.Fatal("old identity accepted")
	}
}

func TestHeapTargetCorruptionOracle(t *testing.T) {
	fs := NewBlockMemFS()
	fs.WriteFile("mariadb/f", []byte("abc"), 0600)
	_, e := fs.freezeHeap("guest", func(h *prepared.Heap) (*prepared.Heap, error) {
		data := make([]byte, prepared.BlockSize)
		copy(data, "bad")
		block, err := prepared.TakeBlock(data, 3)
		if err != nil {
			return nil, err
		}
		f, err := prepared.NewHeapFile(3, []prepared.Block{block}, h.File("f").Digest())
		if err != nil {
			return nil, err
		}
		return prepared.NewHeap(h.Build(), h.Dirs(), map[string]*prepared.HeapFile{"f": f})
	})
	if e == nil {
		t.Fatal("corrupt transferred target accepted")
	}
}

// Exercise actual MemFS/FD/relative-open -> Capture -> Root -> mapRoot wiring.
func TestRootFDAndGenerationIsolation(t *testing.T) {
	fs := NewBlockMemFS()
	fs.MkdirAll("mariadb", 0700)
	fd, e := fs.OpenFile("mariadb/f", os.O_CREATE|os.O_RDWR, 0600)
	if e != nil {
		t.Fatal(e)
	}
	fd.WriteAt([]byte("original"), 0)
	dirfd, _ := fs.OpenFile("mariadb", os.O_RDONLY, 0)
	dir, e := fs.PinDirectory(dirfd)
	if e != nil {
		t.Fatal(e)
	}
	c := &prepared.Capture{}
	if e = c.BindRootSource(fs.RootSource(), "guest"); e != nil {
		t.Fatal(e)
	}
	c.Request()
	if e = fs.FreezeRoot("guest", c); e != nil {
		t.Fatal(e)
	}
	r, e := c.TakeRoot("guest")
	if e != nil {
		t.Fatal(e)
	}
	if _, e = fd.WriteAt([]byte{1}, 0); e == nil {
		t.Fatal("old FD writable")
	}
	if e = fd.Truncate(0); e == nil {
		t.Fatal("old FD truncate")
	}
	if _, e = dir.OpenFile("f", os.O_TRUNC|os.O_RDWR, 0600); e == nil {
		t.Fatal("relative truncation writable")
	}
	for generation := 0; generation < 10; generation++ {
		child := NewBlockMemFS()
		if _, e = mapRoot(child, r, "mariadb"); e != nil {
			t.Fatal(e)
		}
		f, e := child.OpenFile("mariadb/f", os.O_RDWR, 0600)
		if e != nil {
			t.Fatal(e)
		}
		f.WriteAt([]byte{byte(generation)}, prepared.BlockSize-1)
		f.Truncate(prepared.BlockSize + 1)
		f.Truncate(3 * prepared.BlockSize)
		p := make([]byte, 8)
		if _, e = r.File("f").ReadAt(p, 0); e != nil || string(p) != "original" {
			t.Fatal("parent changed", e)
		}
		next := &prepared.Capture{}
		next.BindRootSource(child.RootSource(), "guest")
		next.Request()
		if e = child.FreezeRoot("guest", next); e != nil {
			t.Fatal(e)
		}
		r, e = next.TakeRoot("guest")
		if e != nil {
			t.Fatal(e)
		}
		tail := make([]byte, 2*prepared.BlockSize-1)
		r.File("f").ReadAt(tail, prepared.BlockSize+1)
		if !bytes.Equal(tail, make([]byte, len(tail))) {
			t.Fatal("tail leaked")
		}
	}
}
