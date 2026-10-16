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
