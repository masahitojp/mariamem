package nativewire

import (
	"errors"
	"math"
	"sync"
)

// Experimental host-owned byte window. Outstanding includes queued bytes,
// the peer write in progress and bytes granted but not yet received.
const outputLimit = 65536

type outputWindow struct {
	mu                         sync.Mutex
	changed                    *sync.Cond
	data                       [outputLimit]byte
	head, size, inFlight       int
	received, written, granted uint64
	closed                     bool
}

func newOutputWindow() *outputWindow {
	w := &outputWindow{granted: outputLimit}
	w.changed = sync.NewCond(&w.mu)
	return w
}

func (w *outputWindow) append(offset uint64, data []byte) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.closed {
		return nil
	}
	if offset != w.received || len(data) == 0 || uint64(len(data)) > w.granted-w.received || len(data) > len(w.data)-w.size {
		return errors.New("invalid output offset or host credit")
	}
	for _, b := range data {
		w.data[(w.head+w.size)%len(w.data)] = b
		w.size++
	}
	w.received += uint64(len(data))
	w.changed.Signal()
	return nil
}

func (w *outputWindow) next() ([]byte, bool) {
	w.mu.Lock()
	defer w.mu.Unlock()
	for !w.closed && w.size == 0 {
		w.changed.Wait()
	}
	if w.closed {
		return nil, false
	}
	if w.inFlight != 0 {
		panic("output window has two writers")
	}
	n := min(w.size, 4096)
	b := make([]byte, n)
	for i := range b {
		b[i] = w.data[w.head]
		w.head = (w.head + 1) % len(w.data)
	}
	w.size -= n
	w.inFlight = n
	return b, true
}

func (w *outputWindow) complete(n int) (uint64, uint64, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if n <= 0 || n != w.inFlight || w.written > math.MaxUint64-uint64(n)-outputLimit {
		return 0, 0, errors.New("invalid output completion or credit exhaustion")
	}
	w.written += uint64(n)
	w.granted = w.written + outputLimit
	w.inFlight = 0
	return w.written, w.granted, nil
}

func (w *outputWindow) close() {
	w.mu.Lock()
	w.closed = true
	w.changed.Broadcast()
	w.mu.Unlock()
}
