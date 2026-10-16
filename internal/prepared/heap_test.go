package prepared

import (
	"crypto/sha256"
	"fmt"
	"runtime"
	"testing"
	"weak"
)

func captureWeakImage(t *testing.T, c *Capture) weak.Pointer[Heap] {
	data := make([]byte, BlockSize)
	copy(data, "abc")
	b, e := TakeBlock(data, 3)
	if e != nil {
		t.Fatal(e)
	}
	f, e := NewHeapFile(3, []Block{b}, fmt.Sprintf("%x", sha256.Sum256(data[:3])))
	if e != nil {
		t.Fatal(e)
	}
	h, e := NewHeap("guest", []string{"."}, map[string]*HeapFile{"f": f})
	if e != nil {
		t.Fatal(e)
	}
	ref := weak.Make(h)
	c.Request()
	c.Complete(h)
	if c.TakeResult() != h {
		t.Fatal("capture result lost")
	}
	return ref
}
func TestCompletedCaptureDoesNotRetainImage(t *testing.T) {
	c := &Capture{}
	ref := captureWeakImage(t, c)
	runtime.GC()
	if ref.Value() != nil {
		t.Fatal("transport retains transferred image")
	}
	runtime.KeepAlive(c)
}
