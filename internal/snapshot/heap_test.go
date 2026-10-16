package snapshot

import (
	"crypto/sha256"
	"fmt"
	"github.com/masahitojp/mariamem/internal/prepared"
	"testing"
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
