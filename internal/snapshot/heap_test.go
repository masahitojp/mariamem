package snapshot

import (
	"crypto/sha256"
	"fmt"
	"runtime"
	"testing"
	"weak"

	"github.com/masahitojp/mariamem/internal/prepared"
)

func TestHeapOwnerRejectsCorruptionAndWrongIdentity(t *testing.T) {
	bytes := make([]byte, prepared.BlockSize)
	copy(bytes, "original")
	hash := fmt.Sprintf("%x", sha256.Sum256(bytes))
	block, e := prepared.TakeBlock(bytes, len(bytes))
	if e != nil {
		t.Fatal(e)
	}
	file, e := prepared.NewHeapFile(int64(len(bytes)), []prepared.Block{block}, hash)
	if e != nil {
		t.Fatal(e)
	}
	h, e := prepared.NewHeap("guest", []string{"."}, map[string]*prepared.HeapFile{"f": file})
	if e != nil {
		t.Fatal(e)
	}
	if _, e = OwnHeap(h, "old guest"); e == nil {
		t.Fatal("identity accepted")
	}
	bytes[0] ^= 255 // Deliberately violate producer transfer to exercise owner oracle.
	if _, e = OwnHeap(h, "guest"); e == nil {
		t.Fatal("corruption accepted")
	}
}

//go:noinline
func ownedWeakHeap(t *testing.T) (*Owned, weak.Pointer[prepared.Heap]) {
	t.Helper()
	data := make([]byte, prepared.BlockSize)
	block, err := prepared.TakeBlock(data, len(data))
	if err != nil {
		t.Fatal(err)
	}
	file, err := prepared.NewHeapFile(int64(len(data)), []prepared.Block{block}, fmt.Sprintf("%x", sha256.Sum256(data)))
	if err != nil {
		t.Fatal(err)
	}
	heap, err := prepared.NewHeap("guest", []string{"."}, map[string]*prepared.HeapFile{"f": file})
	if err != nil {
		t.Fatal(err)
	}
	owner, err := OwnHeap(heap, "guest")
	if err != nil {
		t.Fatal(err)
	}
	return owner, weak.Make(heap)
}

func TestClosedOwnerDoesNotRetainHeap(t *testing.T) {
	owner, ref := ownedWeakHeap(t)
	if err := owner.Close(); err != nil {
		t.Fatal(err)
	}
	runtime.GC()
	if ref.Value() != nil {
		t.Fatal("closed owner retains immutable heap")
	}
	runtime.KeepAlive(owner)
}
