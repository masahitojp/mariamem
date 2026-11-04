package base

import (
	"encoding/binary"
	"errors"
	"io"
	"os"
	"sync"
	"sync/atomic"
	"syscall"
	"testing"
	"unsafe"
)

type writeOutcome struct {
	n   int
	err error
}
type outcomeWriter struct {
	outcomes []writeOutcome
	calls    int
}

func (w *outcomeWriter) Write(b []byte) (int, error) {
	w.calls++
	if len(w.outcomes) == 0 {
		return len(b), nil
	}
	r := w.outcomes[0]
	w.outcomes = w.outcomes[1:]
	return r.n, r.err
}

func writeImport(t *testing.T, wide bool, dst io.Writer) (int32, uint64) {
	t.Helper()
	mem := make([]byte, 65536)
	size := new(atomic.Uint64)
	size.Store(uint64(len(mem)))
	m := &Module{Memory: mem, M: unsafe.Pointer(&mem[0]), MemSize: size, MemShared: true, MemMu: new(sync.Mutex), MaxMem: uint64(len(mem))}
	w := DefaultWASI()
	w.SetStdout(dst)
	copy(mem[256:], "abcd")
	if wide {
		binary.LittleEndian.PutUint64(mem[64:], 256)
		binary.LittleEndian.PutUint64(mem[72:], 2)
		binary.LittleEndian.PutUint64(mem[80:], 258)
		binary.LittleEndian.PutUint64(mem[88:], 2)
		rc := w.Fd_write64(m, 1, 64, 2, 128)
		return rc, binary.LittleEndian.Uint64(mem[128:])
	}
	binary.LittleEndian.PutUint32(mem[64:], 256)
	binary.LittleEndian.PutUint32(mem[68:], 2)
	binary.LittleEndian.PutUint32(mem[72:], 258)
	binary.LittleEndian.PutUint32(mem[76:], 2)
	rc := w.Fd_write(m, 1, 64, 2, 128)
	return rc, uint64(binary.LittleEndian.Uint32(mem[128:]))
}

func TestFDWriteReportsErrorsAndProgress(t *testing.T) {
	for _, wide := range []bool{false, true} {
		for _, c := range []struct {
			name     string
			outcomes []writeOutcome
			errno    int32
			n        uint64
			calls    int
		}{
			{"broken-pipe", []writeOutcome{{0, syscall.EPIPE}}, _wasiEPIPE, 0, 1},
			{"wrapped-pipe", []writeOutcome{{0, &os.PathError{Op: "write", Path: "pipe", Err: syscall.EPIPE}}}, _wasiEPIPE, 0, 1},
			{"other-error", []writeOutcome{{0, errors.New("failed")}}, _wasiEIO, 0, 1},
			{"no-progress", []writeOutcome{{0, nil}}, _wasiEIO, 0, 1},
			{"short-progress", []writeOutcome{{1, nil}}, 0, 1, 1},
			{"partial-error", []writeOutcome{{1, syscall.EPIPE}}, 0, 1, 1},
			{"later-error", []writeOutcome{{2, nil}, {0, syscall.EPIPE}}, 0, 2, 2},
			{"complete", nil, 0, 4, 2},
		} {
			name := "wasm32/"
			if wide {
				name = "wasm64/"
			}
			t.Run(name+c.name, func(t *testing.T) {
				w := &outcomeWriter{outcomes: c.outcomes}
				rc, n := writeImport(t, wide, w)
				if rc != c.errno || n != c.n || w.calls != c.calls {
					t.Fatalf("errno=%d bytes=%d calls=%d; want %d/%d/%d", rc, n, w.calls, c.errno, c.n, c.calls)
				}
			})
		}
	}
}

func TestFDWriteClosedPipeIsNotSuccessfulZeroProgress(t *testing.T) {
	for _, wide := range []bool{false, true} {
		reader, writer, err := os.Pipe()
		if err != nil {
			t.Fatal(err)
		}
		reader.Close()
		rc, n := writeImport(t, wide, writer)
		writer.Close()
		if rc != _wasiEPIPE || n != 0 {
			t.Fatalf("wide=%v errno=%d bytes=%d; want EPIPE/0", wide, rc, n)
		}
	}
}
