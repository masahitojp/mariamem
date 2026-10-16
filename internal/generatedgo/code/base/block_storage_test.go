package base

import (
	"bytes"
	"io"
	"math/rand"
	"os"
	"sync"
	"testing"

	"github.com/masahitojp/mariamem/internal/prepared"
)

func TestBlockStorageReference(t *testing.T) {
	for _, seed := range []int64{1, 73, 991} {
		legacy, block := NewMemFS(), NewBlockMemFS()
		a, _ := legacy.OpenFile("f", os.O_CREATE|os.O_RDWR, 0600)
		b, _ := block.OpenFile("f", os.O_CREATE|os.O_RDWR, 0600)
		rng := rand.New(rand.NewSource(seed))
		for step := 0; step < 600; step++ {
			off := int64(rng.Intn(5 * prepared.BlockSize))
			size := rng.Intn(prepared.BlockSize + 5)
			switch rng.Intn(4) {
			case 0:
				p := make([]byte, size)
				rng.Read(p)
				na, ea := a.WriteAt(p, off)
				nb, eb := b.WriteAt(p, off)
				if na != nb || (ea == nil) != (eb == nil) {
					t.Fatalf("write %d: %d %v / %d %v", step, na, ea, nb, eb)
				}
			case 1:
				if e := a.Truncate(off); e != nil {
					t.Fatal(e)
				}
				if e := b.Truncate(off); e != nil {
					t.Fatal(e)
				}
			case 2:
				if e := a.(*memFile).Allocate(off); e != nil {
					t.Fatal(e)
				}
				if e := b.(*memFile).Allocate(off); e != nil {
					t.Fatal(e)
				}
			case 3:
				if _, e := a.Seek(off, io.SeekStart); e != nil {
					t.Fatal(e)
				}
				if _, e := b.Seek(off, io.SeekStart); e != nil {
					t.Fatal(e)
				}
			}
			sa, _ := a.Stat()
			sb, _ := b.Stat()
			if sa.Size() != sb.Size() {
				t.Fatalf("size %d", step)
			}
			pa, pb := make([]byte, sa.Size()+1), make([]byte, sb.Size()+1)
			na, ea := a.ReadAt(pa, 0)
			nb, eb := b.ReadAt(pb, 0)
			if na != nb || (ea == nil) != (eb == nil) || !bytes.Equal(pa, pb) {
				t.Fatalf("content seed %d step %d", seed, step)
			}
			oa, _ := a.Seek(0, io.SeekCurrent)
			ob, _ := b.Seek(0, io.SeekCurrent)
			if oa != ob {
				t.Fatal("position changed")
			}
		}
	}
}
func TestBlockBoundarySparseAndZeroLength(t *testing.T) {
	fs := NewBlockMemFS()
	f, _ := fs.OpenFile("f", os.O_CREATE|os.O_RDWR, 0600)
	for _, off := range []int64{0, prepared.BlockSize - 1, prepared.BlockSize, 2*prepared.BlockSize - 1} {
		p := []byte{1, 2, 3}
		if _, e := f.WriteAt(p, off); e != nil {
			t.Fatal(e)
		}
	}
	if _, e := f.WriteAt(nil, 99*prepared.BlockSize); e != nil {
		t.Fatal(e)
	}
	s, _ := f.Stat()
	if s.Size() != 2*prepared.BlockSize+2 {
		t.Fatal(s.Size())
	}
	if _, e := f.ReadAt(nil, s.Size()+1); e != nil {
		t.Fatal(e)
	}
	if _, e := f.WriteAt([]byte{1}, -1); e == nil {
		t.Fatal("negative write accepted")
	}
	if _, e := f.WriteAt([]byte{1}, int64(^uint64(0)>>1)); e == nil {
		t.Fatal("overflow write accepted")
	}
	if e := f.Truncate(prepared.BlockSize + 1); e != nil {
		t.Fatal(e)
	}
	if e := f.Truncate(3 * prepared.BlockSize); e != nil {
		t.Fatal(e)
	}
	p := make([]byte, 2*prepared.BlockSize-1)
	f.ReadAt(p, prepared.BlockSize+1)
	if !bytes.Equal(p, make([]byte, len(p))) {
		t.Fatal("truncated bytes reappeared")
	}
}
func TestBlockRenameUnlinkAndConcurrentIO(t *testing.T) {
	fs := NewBlockMemFS()
	f, _ := fs.OpenFile("a", os.O_CREATE|os.O_RDWR, 0600)
	if e := fs.Rename("a", "b"); e != nil {
		t.Fatal(e)
	}
	if e := fs.Remove("b"); e != nil {
		t.Fatal(e)
	}
	if e := f.Truncate(4 * prepared.BlockSize); e != nil {
		t.Fatal(e)
	}
	var wg sync.WaitGroup
	stop := make(chan struct{})
	readDone := make(chan struct{})
	go func() {
		defer close(readDone)
		p := make([]byte, prepared.BlockSize)
		for {
			select {
			case <-stop:
				return
			default:
			}
			// Every whole-block write is serialized with this same-file read.
			if _, e := f.ReadAt(p, 0); e != nil {
				t.Error(e)
				return
			}
			if !bytes.Equal(p, bytes.Repeat(p[:1], len(p))) {
				t.Error("torn block during concurrent read/write")
				return
			}
		}
	}()
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			for n := 0; n < 100; n++ {
				if _, e := f.WriteAt(bytes.Repeat([]byte{byte(i + 1)}, prepared.BlockSize), int64(i*prepared.BlockSize)); e != nil {
					t.Error(e)
				}
			}
		}(i)
	}
	wg.Wait()
	close(stop)
	<-readDone
	p := make([]byte, 4*prepared.BlockSize)
	if _, e := f.ReadAt(p, 0); e != nil {
		t.Fatal(e)
	}
	for i := 0; i < 4; i++ {
		if !bytes.Equal(p[i*prepared.BlockSize:(i+1)*prepared.BlockSize], bytes.Repeat([]byte{byte(i + 1)}, prepared.BlockSize)) {
			t.Fatal("overlap")
		}
	}
	if _, e := fs.Stat("b"); !os.IsNotExist(e) {
		t.Fatal("unlink lost")
	}
}

func TestBlockRelativeOpenTruncateAndAppend(t *testing.T) {
	fs := NewBlockMemFS()
	fs.MkdirAll("dir", 0700)
	handle, _ := fs.OpenFile("dir", os.O_RDONLY, 0)
	dir, e := fs.PinDirectory(handle)
	if e != nil {
		t.Fatal(e)
	}
	f, e := dir.OpenFile("f", os.O_CREATE|os.O_RDWR, 0600)
	if e != nil {
		t.Fatal(e)
	}
	if f.(*memFile).node.blocks == nil {
		t.Fatal("relative path bypassed block storage")
	}
	f.Write([]byte("before"))
	f, e = dir.OpenFile("f", os.O_TRUNC|os.O_RDWR, 0600)
	if e != nil {
		t.Fatal(e)
	}
	st, _ := f.Stat()
	if st.Size() != 0 {
		t.Fatal("relative truncate ignored")
	}
	f.Write([]byte("a"))
	f, e = dir.OpenFile("f", os.O_APPEND|os.O_RDWR, 0600)
	if e != nil {
		t.Fatal(e)
	}
	f.Write([]byte("b"))
	p := make([]byte, 2)
	if _, e = f.ReadAt(p, 0); e != nil || string(p) != "ab" {
		t.Fatalf("%s %v", p, e)
	}
}
