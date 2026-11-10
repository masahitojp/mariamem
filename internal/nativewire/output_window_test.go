package nativewire

import (
	"bytes"
	"math"
	"testing"
)

func TestOutputCreditIncludesPeerWrite(t *testing.T) {
	w := newOutputWindow()
	if e := w.append(0, make([]byte, outputLimit)); e != nil {
		t.Fatal(e)
	}
	b, _ := w.next()
	if e := w.append(outputLimit, []byte{1}); e == nil {
		t.Fatal("in-flight write freed credit early")
	}
	ack, limit, e := w.complete(len(b))
	if e != nil || ack != uint64(len(b)) || limit != ack+outputLimit {
		t.Fatal(ack, limit, e)
	}
	if e = w.append(outputLimit, make([]byte, len(b))); e != nil {
		t.Fatal(e)
	}
}

func TestOutputCreditByteQueueWrapAndFragments(t *testing.T) {
	w := newOutputWindow()
	want := make([]byte, 200000)
	for i := range want {
		want[i] = byte(i % 251)
	}
	sent := 0
	var got []byte
	for len(got) < len(want) {
		for sent < len(want) && uint64(sent) < w.granted {
			n := min(1+sent%53, len(want)-sent, int(w.granted)-sent)
			if e := w.append(uint64(sent), want[sent:sent+n]); e != nil {
				t.Fatal(e)
			}
			sent += n
		}
		b, ok := w.next()
		if !ok {
			t.Fatal("closed")
		}
		got = append(got, b...)
		if _, _, e := w.complete(len(b)); e != nil {
			t.Fatal(e)
		}
	}
	if !bytes.Equal(got, want) {
		t.Fatal("byte ordering/corruption")
	}
}

func TestOutputCreditRejectsOffsetsAndExhaustion(t *testing.T) {
	w := newOutputWindow()
	if e := w.append(1, []byte{1}); e == nil {
		t.Fatal("gap")
	}
	if e := w.append(0, []byte{1}); e != nil {
		t.Fatal(e)
	}
	if e := w.append(0, []byte{1}); e == nil {
		t.Fatal("duplicate")
	}
	w.next()
	if _, _, e := w.complete(2); e == nil {
		t.Fatal("wrong completion")
	}
	w.written = math.MaxUint64 - outputLimit
	if _, _, e := w.complete(1); e == nil {
		t.Fatal("wrapped grant")
	}
}

func TestOutputCloseWakesBlockedWriter(t *testing.T) {
	w := newOutputWindow()
	done := make(chan bool, 1)
	go func() { _, ok := w.next(); done <- ok }()
	w.close()
	if <-done {
		t.Fatal("write after close")
	}
}
