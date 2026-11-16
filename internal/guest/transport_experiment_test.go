package guest

import (
	"bytes"
	"io"
	"testing"
	"time"
)

func TestExperimentResponsePipe(t *testing.T) {
	for _, mode := range []string{"os", "go"} {
		t.Run(mode, func(t *testing.T) {
			t.Setenv("RESPONSE_PIPE", mode)
			t.Run("fragmented_large_and_empty", func(t *testing.T) {
				r, w, e := experimentResponsePipe()
				if e != nil {
					t.Fatal(e)
				}
				defer r.Close()
				defer w.Close()
				payload := bytes.Repeat([]byte("frame-body"), 10000)
				done := make(chan error, 1)
				go func() {
					for _, b := range [][]byte{payload[:1], {}, payload[1:3], payload[3:]} {
						if _, e := w.Write(b); e != nil {
							done <- e
							return
						}
					}
					done <- w.Close()
				}()
				got, e := io.ReadAll(r)
				if e != nil || !bytes.Equal(got, payload) {
					t.Fatalf("bytes/error: %d %v", len(got), e)
				}
				if e = <-done; e != nil {
					t.Fatal(e)
				}
			})
			t.Run("close_unblocks_write", func(t *testing.T) {
				r, w, e := experimentResponsePipe()
				if e != nil {
					t.Fatal(e)
				}
				defer w.Close()
				done := make(chan error, 1)
				go func() { _, e := w.Write(make([]byte, 4<<20)); done <- e }()
				r.Close()
				select {
				case e := <-done:
					if e == nil {
						t.Fatal("expected failed write")
					}
				case <-time.After(time.Second):
					t.Fatal("write stuck")
				}
			})
			t.Run("close_unblocks_read", func(t *testing.T) {
				r, w, e := experimentResponsePipe()
				if e != nil {
					t.Fatal(e)
				}
				defer r.Close()
				done := make(chan error, 1)
				go func() { _, e := r.Read(make([]byte, 4)); done <- e }()
				w.Close()
				select {
				case e := <-done:
					if e != io.EOF {
						t.Fatalf("expected EOF: %v", e)
					}
				case <-time.After(time.Second):
					t.Fatal("read stuck")
				}
			})
		})
	}
}
