package nativewire

import (
	"io"
	"sync"
)

// bytePipe is the bounded stream between a linked guest and its host.
// Closing the writer preserves buffered data. Closing the reader interrupts writes.
type bytePipe struct {
	mu                         sync.Mutex
	changed                    *sync.Cond
	writers                    sync.Mutex // keep a Write contiguous across waits for space
	buf                        [16 << 10]byte
	readAt, used               int
	readerClosed, writerClosed bool
}
type byteReader struct{ p *bytePipe }
type byteWriter struct{ p *bytePipe }

func newBytePipe() (byteReader, byteWriter) {
	p := new(bytePipe)
	p.changed = sync.NewCond(&p.mu)
	return byteReader{p}, byteWriter{p}
}
func (r byteReader) Read(dst []byte) (int, error) {
	p := r.p
	p.mu.Lock()
	defer p.mu.Unlock()
	for p.used == 0 && !p.readerClosed && !p.writerClosed && len(dst) > 0 {
		p.changed.Wait()
	}
	if p.readerClosed {
		return 0, io.ErrClosedPipe
	}
	if len(dst) == 0 {
		return 0, nil
	}
	if p.used == 0 {
		return 0, io.EOF
	}
	n := min(len(dst), p.used)
	first := copy(dst[:n], p.buf[p.readAt:])
	copy(dst[first:n], p.buf[:n-first])
	p.readAt = (p.readAt + n) % len(p.buf)
	p.used -= n
	p.changed.Broadcast()
	return n, nil
}
func (w byteWriter) Write(src []byte) (int, error) {
	p := w.p
	p.writers.Lock()
	defer p.writers.Unlock()
	p.mu.Lock()
	defer p.mu.Unlock()
	written := 0
	for {
		if p.readerClosed || p.writerClosed {
			return written, io.ErrClosedPipe
		}
		if written == len(src) {
			return written, nil
		}
		if p.used == len(p.buf) {
			p.changed.Wait()
			continue
		}
		start := (p.readAt + p.used) % len(p.buf)
		n := min(len(p.buf)-p.used, len(src)-written)
		chunk := src[written : written+n]
		first := copy(p.buf[start:], chunk)
		copy(p.buf[:], chunk[first:])
		p.used += n
		written += n
		p.changed.Broadcast()
	}
}
func (r byteReader) Close() error {
	p := r.p
	p.mu.Lock()
	defer p.mu.Unlock()
	p.readerClosed = true
	p.changed.Broadcast()
	return nil
}
func (w byteWriter) Close() error {
	p := w.p
	p.mu.Lock()
	defer p.mu.Unlock()
	p.writerClosed = true
	p.changed.Broadcast()
	return nil
}
