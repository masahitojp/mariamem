package prepared

import (
	"bytes"
	"crypto/sha256"
	"fmt"
	"io"
	"math/rand"
	"runtime"
	"testing"
	"weak"
)

func rootFixture(t *testing.T) (*Capture, *RootSource, *FileStore) {
	t.Helper()
	s := NewRootSource(true)
	f := NewFileStore(s)
	if _, e := f.WriteAt([]byte("original"), 0); e != nil {
		t.Fatal(e)
	}
	c := &Capture{}
	if e := c.BindRootSource(s, "guest"); e != nil {
		t.Fatal(e)
	}
	c.Request()
	image, e := f.Seal()
	if e != nil {
		t.Fatal(e)
	}
	if e = c.CompleteRoot(s, "guest", []string{"."}, map[string]*FrozenFile{"f": image}); e != nil {
		t.Fatal(e)
	}
	return c, s, f
}
func TestRootCaptureRejectsSubstitution(t *testing.T) {
	for _, kind := range []string{"other-root", "identity", "source", "missing", "extra", "size", "block", "discard"} {
		t.Run(kind, func(t *testing.T) {
			c, s, _ := rootFixture(t)
			switch kind {
			case "other-root":
				other, _, _ := rootFixture(t)
				c.native = other.native
			case "identity":
				c.native.build = "other"
			case "source":
				c.native.source = NewRootSource(false)
			case "missing":
				delete(c.native.files, "f")
			case "extra":
				c.native.files["extra"] = c.native.files["f"]
			case "size":
				c.native.files["f"].data.size++
			case "block":
				f := c.native.files["f"]
				b := f.data.blocks[0]
				b.block.data = make([]byte, BlockSize)
				f.data.blocks[0] = b
			case "discard":
				c.Discard()
			}
			if r, e := c.TakeRoot("guest"); e == nil || r != nil {
				t.Fatal("substitution accepted")
			}
			c.Discard()
			for k, v := range s.Counts() {
				if len(k) >= 7 && k[:7] == "freeze/" && (v.Read+v.Copy+v.Hash+v.Zero) != 0 {
					t.Fatal(k, v)
				}
			}
		})
	}
	c, s, _ := rootFixture(t)
	foreign := NewRootSource(false)
	if e := c.CompleteRoot(foreign, "guest", []string{"."}, c.native.files); e == nil {
		t.Fatal("foreign completion accepted")
	}
	r, e := c.TakeRoot("guest")
	if e != nil {
		t.Fatal(e)
	}
	if _, e = c.TakeRoot("guest"); e == nil {
		t.Fatal("replay accepted")
	}
	if r.source != s {
		t.Fatal("wrong root")
	}
}
func TestRootStorageReferenceAndIsolation(t *testing.T) {
	for _, seed := range []int64{1, 73, 991} {
		s := NewRootSource(true)
		f := NewFileStore(s)
		ref := []byte{}
		rng := rand.New(rand.NewSource(seed))
		for step := 0; step < 500; step++ {
			off := rng.Intn(5 * BlockSize)
			switch rng.Intn(3) {
			case 0:
				p := make([]byte, rng.Intn(BlockSize+3))
				rng.Read(p)
				_, e := f.WriteAt(p, int64(off))
				if e != nil {
					t.Fatal(e)
				}
				if len(p) > 0 {
					if off+len(p) > len(ref) {
						ref = append(ref, make([]byte, off+len(p)-len(ref))...)
					}
					copy(ref[off:], p)
				}
			case 1:
				if e := f.Resize(int64(off)); e != nil {
					t.Fatal(e)
				}
				if off < len(ref) {
					ref = append([]byte(nil), ref[:off]...)
				} else {
					ref = append(ref, make([]byte, off-len(ref))...)
				}
			case 2:
				if step%25 == 0 {
					image, e := f.Seal()
					if e != nil {
						t.Fatal(e)
					}
					if _, e = f.WriteAt([]byte{1}, 0); e == nil {
						t.Fatal("old writer")
					}
					if e = f.Resize(1); e == nil {
						t.Fatal("old resize")
					}
					f = image.Fork(NewRootSource(true))
					p := make([]byte, len(ref)+1)
					n, e := image.ReadAt(p, 0)
					if n != len(ref) || e != io.EOF || !bytes.Equal(p[:n], ref) {
						t.Fatal("fixed content")
					}
				}
			}
			p := make([]byte, len(ref)+1)
			n, e := f.ReadAt(p, 0)
			if n != len(ref) || e != io.EOF || !bytes.Equal(p[:n], ref) {
				t.Fatalf("seed %d step %d", seed, step)
			}
		}
	}
}
func TestRootCorruptionDetectionDifference(t *testing.T) {
	c, _, _ := rootFixture(t)
	expected := fmt.Sprintf("%x", sha256.Sum256([]byte("original")))
	c.native.files["f"].data.blocks[0].block.data[0] ^= 255
	r, e := c.TakeRoot("guest")
	if e != nil {
		t.Fatal(e)
	}
	h, e := r.File("f").LegacyFile()
	if e != nil {
		t.Fatal(e)
	}
	if h.Digest() == expected {
		t.Fatal("injection did not change contents")
	}
	strictFile, e := NewHeapFile(h.Size(), h.Blocks(), expected)
	if e != nil {
		t.Fatal(e)
	}
	strict, e := NewHeap("guest", []string{"."}, map[string]*HeapFile{"f": strictFile})
	if e != nil {
		t.Fatal(e)
	}
	if e = strict.Verify("guest"); e == nil {
		t.Fatal("strict corruption accepted")
	}
	t.Log("LIMITATION: root ownership accepted private-byte mutation; independent expected digest differs")
}
func TestRootCaptureReclamation(t *testing.T) {
	c, _, f := rootFixture(t)
	ref := weak.Make(c.native)
	c.Discard()
	runtime.GC()
	if ref.Value() != nil {
		t.Fatal("discarded capture retains root")
	}
	runtime.KeepAlive(c)
	runtime.KeepAlive(f)
	c, _, f = rootFixture(t)
	r, e := c.TakeRoot("guest")
	if e != nil {
		t.Fatal(e)
	}
	ref = weak.Make(r)
	child := r.File("f").Fork(NewRootSource(false))
	r = nil
	runtime.GC()
	if ref.Value() != nil {
		t.Fatal("capture/child retains parent root")
	}
	p := make([]byte, 8)
	if _, e := child.ReadAt(p, 0); e != nil || string(p) != "original" {
		t.Fatal("child lifetime", e)
	}
	runtime.KeepAlive(child)
	runtime.KeepAlive(c)
	runtime.KeepAlive(f)
}
