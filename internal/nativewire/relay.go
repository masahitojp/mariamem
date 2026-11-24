package nativewire

import (
	"errors"
	"io"
	"net"
	"sync"
)

const outputLimit uint64 = 65536

type key struct {
	slot       uint32
	generation uint64
}
type session struct {
	lease *Lease
	phase string

	root           *Backend
	id             key
	conn           net.Conn
	mu             sync.Mutex
	cv             *sync.Cond
	sent, consumed uint64
	dead           bool
	outFrames      []frame
	outBytes       uint64
	outWake        chan struct{}
	ended          chan struct{}

	// Protected by root.mu: tracks output bytes already written to conn whose
	// kindAck has not yet finished sending, plus whether the current command
	// has already delivered output bytes to conn.
	ackTarget uint64
	ackSent   uint64
	cmdAcked  bool
}

func (s *session) pushOutput(f frame) bool {
	s.mu.Lock()
	if s.dead {
		s.mu.Unlock()
		return true
	}
	n := uint64(len(f.body))
	if n == 0 || n > outputLimit-s.outBytes {
		s.mu.Unlock()
		return false
	}
	if last := len(s.outFrames) - 1; last >= 0 {
		prev := &s.outFrames[last]
		if prev.value+uint64(len(prev.body)) == f.value && len(prev.body)+len(f.body) <= 4096 {
			prev.body = append(prev.body, f.body...)
			s.outBytes += n
			s.mu.Unlock()
			select {
			case s.outWake <- struct{}{}:
			default:
			}
			return true
		}
	}
	f.body = append([]byte(nil), f.body...)
	s.outFrames = append(s.outFrames, f)
	s.outBytes += n
	s.mu.Unlock()
	select {
	case s.outWake <- struct{}{}:
	default:
	}
	return true
}

func (s *session) popOutput() (frame, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.dead || len(s.outFrames) == 0 {
		return frame{}, false
	}
	f := s.outFrames[0]
	s.outFrames[0] = frame{}
	s.outFrames = s.outFrames[1:]
	if len(s.outFrames) == 0 {
		s.outFrames = nil
	}
	return f, true
}

func (s *session) releaseOutputBytes(n uint64) {
	s.mu.Lock()
	if n >= s.outBytes {
		s.outBytes = 0
	} else {
		s.outBytes -= n
	}
	s.mu.Unlock()
}

func (s *session) hasQueuedOutput() bool {
	s.mu.Lock()
	queued := !s.dead && s.outBytes > 0
	s.mu.Unlock()
	return queued
}

func (s *session) close() {
	s.mu.Lock()
	if !s.dead {
		s.dead = true
		s.outFrames = nil
		s.outBytes = 0
		close(s.ended)
		s.conn.Close()
		s.cv.Broadcast()
	}
	s.mu.Unlock()
}

func (r *Backend) reserveLocked(c net.Conn) (*session, error) {
	l, e := r.owner.ReserveLocked()
	if e != nil {
		return nil, e
	}
	t := l.Token()
	s := &session{root: r, lease: l, id: key{t.Slot, t.Generation}, conn: c, outWake: make(chan struct{}, 1), ended: make(chan struct{})}
	s.cv = sync.NewCond(&s.mu)
	r.sessions[s.id] = s
	r.notifyDisconnectLocked()
	r.notifyActivityLocked()
	return s, nil
}
func (s *session) relayDone(part uint8) {
	r := s.root
	r.mu.Lock()
	released, e := r.owner.RelayDoneLocked(s.lease, part)
	if released {
		delete(r.sessions, s.id)
		r.notifyDisconnectLocked()
		r.notifyActivityLocked()
	}
	r.mu.Unlock()
	if e != nil {
		r.fail(e)
	}
}
func (r *Backend) nativeRetired(s *session) {
	s.close()
	r.mu.Lock()
	released, e := r.owner.NativeRetiredLocked(s.lease)
	if released {
		delete(r.sessions, s.id)
		r.notifyDisconnectLocked()
		r.notifyActivityLocked()
	}
	r.mu.Unlock()
	if e != nil {
		r.fail(e)
	}
}
func (r *Backend) attach(s *session) {
	c := s.conn
	writerStarted := false
	defer s.relayDone(Reader)
	defer func() {
		if !writerStarted {
			s.relayDone(Writer)
		}
	}()
	r.mu.Lock()
	e := r.owner.BeginOpenLocked(s.lease)
	if e != nil {
		r.owner.CancelReservedLocked(s.lease)
	}
	r.mu.Unlock()
	if e != nil {
		s.close()
		return
	}
	f, e := r.rpc(frame{kind: kindOpen, slot: s.id.slot, generation: s.id.generation, value: r.limit}, s)
	if e != nil {
		// A lost OPEN reply is uncertain: retain the reservation until disposal.
		r.mu.Lock()
		stopping := r.stopping
		r.owner.UncertainLocked(s.lease)
		r.mu.Unlock()
		if !stopping || !errors.Is(e, ErrClosed) {
			r.fail(e)
		}
		c.Close()
		return
	}
	if f.kind != kindOpened {
		if f.kind != kindRejected || f.value != 4 {
			r.fail(errors.New("invalid OPEN reply"))
		}
		s.close()
		c.Close()
		return
	}
	r.mu.Lock()
	closing := r.stopping
	if !closing {
		r.wg.Add(1)
	}
	r.mu.Unlock()
	if closing {
		s.close()
		return
	}
	writerStarted = true
	go func() {
		defer r.wg.Done()
		defer s.relayDone(Writer)
		defer func() {
			r.mu.Lock()
			if s.ackTarget != s.ackSent {
				s.ackTarget = s.ackSent
				r.notifyActivityLocked()
			}
			r.mu.Unlock()
		}()
		defer s.close()
		for {
			f, ok := s.popOutput()
			if !ok {
				select {
				case <-s.outWake:
					continue
				case <-s.ended:
					return
				}
			}
			b := f.body
			for len(b) > 0 {
				n, e := c.Write(b)
				if e != nil {
					r.mu.Lock()
					stopping := r.stopping
					r.mu.Unlock()
					s.mu.Lock()
					ownerClosed := s.dead
					s.mu.Unlock()
					if !stopping && !ownerClosed {
						_ = r.send(frame{kind: kindPeerEOF, slot: s.id.slot, generation: s.id.generation, value: 1})
					}
					return
				}
				if n <= 0 || n > len(b) {
					r.fail(io.ErrNoProgress)
					return
				}
				b = b[n:]
			}
			end := f.value + uint64(len(f.body))
			// Advance ackTarget BEFORE releasing outBytes so SnapshotHeap never
			// sees a gap where outBytes==0 and ackSent==ackTarget while kindAck
			// has not yet been written to the guest control stream.
			r.mu.Lock()
			if end > s.ackTarget {
				s.ackTarget = end
			}
			s.cmdAcked = true
			hook := r.beforeAck
			r.mu.Unlock()
			s.releaseOutputBytes(uint64(len(f.body)))
			if hook != nil {
				hook(s.id, end)
			}
			if e := r.send(frame{kind: kindAck, slot: s.id.slot, generation: s.id.generation, value: end}); e != nil {
				return
			}
			r.mu.Lock()
			if end > s.ackSent {
				s.ackSent = end
			}
			r.notifyActivityLocked()
			r.mu.Unlock()
		}
	}()
	defer func() {
		r.mu.Lock()
		stopping := r.stopping
		r.mu.Unlock()
		if !stopping {
			r.send(frame{kind: kindPeerEOF, slot: s.id.slot, generation: s.id.generation})
		}
	}()
	b := make([]byte, 4096)
	for {
		s.mu.Lock()
		for !s.dead && s.sent-s.consumed > inputLimit {
			s.cv.Wait()
		}
		if s.dead {
			s.mu.Unlock()
			return
		}
		// One bounded observation byte beyond the credit window lets native
		// input() decide overflow under the same gate as capture. It is never
		// appended above the guest queue limit. EOF stays observable at full.
		available := uint64(inputLimit) - (s.sent - s.consumed) + 1
		offset := s.sent
		s.mu.Unlock()
		size := len(b)
		if uint64(size) > available {
			size = int(available)
		}
		n, e := c.Read(b[:size])
		if n > 0 {
			s.mu.Lock()
			s.sent += uint64(n)
			s.mu.Unlock()
			if sendErr := r.send(frame{kind: kindData, slot: s.id.slot, generation: s.id.generation, value: offset, body: b[:n]}); sendErr != nil {
				return
			}
		}
		if e != nil {
			return
		}
	}
}
