package base

import (
	"bytes"
	"io"
	"os"
	"testing"
)

func TestMemFSGrowthAmortizedCopy(t *testing.T) {
	fs := NewMemFS()
	opened, err := fs.OpenFile("copy", os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		t.Fatal(err)
	}
	f := opened.(*memFile)
	const size = 4 << 20
	block := bytes.Repeat([]byte{42}, 65536) // unchanged guest Snapshot block
	var copied, allocated int64
	for written := 0; written < size; written += len(block) {
		old := f.node.data
		if _, err := f.Write(block); err != nil {
			t.Fatal(err)
		}
		if len(old) == 0 || &old[0] != &f.node.data[0] {
			copied += int64(len(old))
			allocated += int64(cap(f.node.data))
		}
		st, err := f.Stat()
		if err != nil || st.Size() != int64(written+len(block)) {
			t.Fatalf("logical size: %v %v", st, err)
		}
	}
	// Deterministic work bound, independent of GC/timing/CPU scheduling.
	// Exact-size growth copies 126 MiB for this 4 MiB file and fails here.
	if copied > 8*size || allocated > 10*size {
		t.Fatalf("quadratic growth: copied=%d allocated=%d file=%d", copied, allocated, size)
	}
	if _, err := f.Seek(0, io.SeekStart); err != nil {
		t.Fatal(err)
	}
	got, err := io.ReadAll(f)
	if err != nil || !bytes.Equal(got, bytes.Repeat([]byte{42}, size)) {
		t.Fatalf("copy contents: len=%d err=%v", len(got), err)
	}
	var one [1]byte
	if n, err := f.ReadAt(one[:], size); n != 0 || err != io.EOF {
		t.Fatalf("capacity leaked as file content: %d %v", n, err)
	}
}

func TestMemFSGrowthZeroFillAndOffsets(t *testing.T) {
	fs := NewMemFS()
	opened, err := fs.OpenFile("file", os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		t.Fatal(err)
	}
	f := opened.(*memFile)
	initial := bytes.Repeat([]byte{99}, 4096)
	if _, err := f.Write(initial); err != nil {
		t.Fatal(err)
	}
	if err := f.Truncate(7); err != nil {
		t.Fatal(err)
	}
	if err := f.Truncate(2048); err != nil {
		t.Fatal(err)
	}
	if f.off != 4096 {
		t.Fatalf("truncate changed offset: %d", f.off)
	}
	if !bytes.Equal(f.node.data[:7], initial[:7]) || !bytes.Equal(f.node.data[7:], make([]byte, 2048-7)) {
		t.Fatal("truncate/regrow exposed stale bytes")
	}
	if err := f.Truncate(3); err != nil {
		t.Fatal(err)
	}
	if _, err := f.WriteAt([]byte("x"), 3000); err != nil {
		t.Fatal(err)
	}
	if f.off != 4096 || len(f.node.data) != 3001 || !bytes.Equal(f.node.data[3:3000], make([]byte, 2997)) {
		t.Fatal("sparse write or WriteAt offset incorrect")
	}
	if _, err := f.WriteAt([]byte("y"), 6000); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(f.node.data[3001:6000], make([]byte, 2999)) {
		t.Fatal("allocation growth hole not zero")
	}
	other, err := fs.OpenFile("file", os.O_RDWR|os.O_TRUNC, 0)
	if err != nil {
		t.Fatal(err)
	}
	if st, err := f.Stat(); err != nil || st.Size() != 0 {
		t.Fatalf("O_TRUNC: %v %v", st, err)
	}
	if _, err := other.Write([]byte("abc")); err != nil {
		t.Fatal(err)
	}
	if err := f.Truncate(6000); err != nil {
		t.Fatal(err)
	}
	if string(f.node.data[:3]) != "abc" || !bytes.Equal(f.node.data[3:], make([]byte, 5997)) {
		t.Fatal("O_TRUNC/regrow stale bytes")
	}
	appendFD, err := fs.OpenFile("file", os.O_WRONLY|os.O_APPEND, 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := appendFD.Write([]byte("end")); err != nil {
		t.Fatal(err)
	}
	if len(f.node.data) != 6003 || string(f.node.data[6000:]) != "end" {
		t.Fatal("append used capacity instead of length")
	}
}
