package guest

import (
	"bytes"
	"errors"
	"io"
	"sync"
	"testing"
	"time"
)

func TestWrapAndDrain(t *testing.T) {
	r, w := newBytePipe()
	if n, err := w.Write(nil); n != 0 || err != nil {
		t.Fatal(n, err)
	}
	input := bytes.Repeat([]byte("order-items\x00"), 9000)
	done := make(chan error, 1)
	go func() {
		n, err := w.Write(input)
		if err == nil && n != len(input) {
			err = io.ErrShortWrite
		}
		w.Close()
		done <- err
	}()
	var result bytes.Buffer
	tmp := make([]byte, 733)
	for {
		n, err := r.Read(tmp)
		result.Write(tmp[:n])
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
	}
	if err := <-done; err != nil || !bytes.Equal(input, result.Bytes()) {
		t.Fatal("stream mismatch", err)
	}
	if n, err := w.Write([]byte{1}); n != 0 || !errors.Is(err, io.ErrClosedPipe) {
		t.Fatal(n, err)
	}
}
func TestFullPipeClose(t *testing.T) {
	for _, closeReader := range []bool{true, false} {
		r, w := newBytePipe()
		if _, err := w.Write(make([]byte, len(r.p.buf))); err != nil {
			t.Fatal(err)
		}
		result := make(chan error, 1)
		go func() { _, err := w.Write([]byte{9}); result <- err }()
		if closeReader {
			r.Close()
			r.Close()
		} else {
			w.Close()
			w.Close()
		}
		select {
		case err := <-result:
			if !errors.Is(err, io.ErrClosedPipe) {
				t.Fatal(err)
			}
		case <-time.After(2 * time.Second):
			t.Fatal("writer did not return")
		}
	}
}
func TestReadCloseAndWriters(t *testing.T) {
	r, w := newBytePipe()
	done := make(chan error, 1)
	go func() { _, err := r.Read(make([]byte, 1)); done <- err }()
	r.Close()
	if err := <-done; !errors.Is(err, io.ErrClosedPipe) {
		t.Fatal(err)
	}
	r, w = newBytePipe()
	var group sync.WaitGroup
	a := bytes.Repeat([]byte{9}, 40000)
	b := bytes.Repeat([]byte{4}, 40000)
	for _, v := range [][]byte{a, b} {
		group.Add(1)
		go func(v []byte) {
			defer group.Done()
			if n, err := w.Write(v); n != len(v) || err != nil {
				t.Errorf("write %d %v", n, err)
			}
		}(v)
	}
	go func() { group.Wait(); w.Close() }()
	all, err := io.ReadAll(r)
	if err != nil || !(bytes.Equal(all, append(append([]byte{}, a...), b...)) || bytes.Equal(all, append(append([]byte{}, b...), a...))) {
		t.Fatal("interleaved writes", err)
	}
}

func TestCloseAfterPartialLargeWrite(t *testing.T) {
	r, w := newBytePipe()
	capacity := len(r.p.buf)
	type outcome struct {
		n   int
		err error
	}
	result := make(chan outcome, 1)
	go func() {
		n, err := w.Write(make([]byte, capacity*3))
		result <- outcome{n, err}
	}()
	// A returned byte proves that Write started. Without another reader the
	// same Write cannot finish, even if it refills the single freed byte.
	if _, err := io.ReadFull(r, make([]byte, 1)); err != nil {
		t.Fatal(err)
	}
	r.Close()
	select {
	case got := <-result:
		if !errors.Is(got.err, io.ErrClosedPipe) || got.n < capacity || got.n > capacity+1 {
			t.Fatal(got)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("partial large write did not stop")
	}
}
