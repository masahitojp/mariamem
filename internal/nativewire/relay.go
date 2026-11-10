package nativewire

import (
	"errors"
	"io"
	"net"
	"sync"
)

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
	output         *outputWindow
	ended          chan struct{}
}

func (s *session) close() {
	s.mu.Lock()
	if !s.dead {
		s.dead = true
		close(s.ended)
		s.conn.Close()
		s.output.close()
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
	s := &session{root: r, lease: l, id: key{t.Slot, t.Generation}, conn: c, output: newOutputWindow(), ended: make(chan struct{})}
	s.cv = sync.NewCond(&s.mu)
	r.sessions[s.id] = s
	return s, nil
}
func (s *session) relayDone(part uint8) {
	r := s.root
	r.mu.Lock()
	released, e := r.owner.RelayDoneLocked(s.lease, part)
	if released {
		delete(r.sessions, s.id)
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
		r.owner.UncertainLocked(s.lease)
		r.mu.Unlock()
		r.fail(e)
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
		defer s.close()
		for {
			data, ok := s.output.next()
			if !ok {
				return
			}
			b := data
			for len(b) > 0 {
				n, e := c.Write(b)
				if e != nil {
					r.send(frame{kind: kindPeerEOF, slot: s.id.slot, generation: s.id.generation, value: 1})
					return
				}
				if n <= 0 || n > len(b) {
					r.fail(io.ErrNoProgress)
					return
				}
				b = b[n:]
			}
			ack, grant, err := s.output.complete(len(data))
			if err != nil {
				r.fail(err)
				return
			}
			if err = r.send(frame{kind: kindAck, slot: s.id.slot, generation: s.id.generation, value: ack}); err != nil {
				return
			}
			if err = r.send(frame{kind: kindOutputGrant, slot: s.id.slot, generation: s.id.generation, value: grant}); err != nil {
				return
			}
		}
	}()
	if err := r.send(frame{kind: kindOutputGrant, slot: s.id.slot, generation: s.id.generation, value: outputLimit}); err != nil {
		r.fail(err)
		return
	}
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
