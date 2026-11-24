package nativewire

import (
	"context"
	"errors"
	"net"
)

// DialContext performs admission before starting any OPEN/relay worker. The
// returned connection belongs to the caller; ctx does not own its later life.
func (r *Backend) DialContext(ctx context.Context) (net.Conn, error) {
	if e := ctx.Err(); e != nil {
		return nil, e
	}
	for {
		r.mu.Lock()
		if e := ctx.Err(); e != nil {
			r.mu.Unlock()
			return nil, e
		}
		if r.stopping || r.checking || r.consumed || r.failure != nil {
			r.mu.Unlock()
			return nil, ErrClosed
		}
		if r.keepHold && r.keepReleased != nil {
			wait := r.keepReleased
			r.mu.Unlock()
			select {
			case <-wait:
				continue
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-r.failed:
				return nil, ErrClosed
			case <-r.done:
				return nil, ErrClosed
			}
		}
		client, server := net.Pipe()
		s, e := r.reserveLocked(server)
		if e != nil {
			r.mu.Unlock()
			_ = client.Close()
			_ = server.Close()
			if errors.Is(e, ErrExhausted) {
				go r.fail(e)
			}
			return nil, e
		}
		r.wg.Add(1)
		r.mu.Unlock()
		go func() { defer r.wg.Done(); r.attach(s) }()
		return client, nil
	}
}

// Serve transfers listener ownership to this backend. The caller handles a
// net.Listen failure by closing the backend through its same typed disposer.
func (r *Backend) Serve(l net.Listener) error {
	if l == nil {
		return errors.New("native listener required")
	}
	r.mu.Lock()
	if r.listener != nil || r.stopping || r.checking || r.consumed || r.failure != nil {
		r.mu.Unlock()
		_ = l.Close()
		return ErrClosed
	}
	r.listener = l
	r.wg.Add(1)
	r.mu.Unlock()
	go func() {
		defer r.wg.Done()
		for {
			c, e := l.Accept()
			if e != nil {
				r.mu.Lock()
				normal := r.stopping
				r.mu.Unlock()
				if !normal {
					r.fail(e)
				}
				return
			}
			var s *session
			var deny bool
			for {
				r.mu.Lock()
				deny = r.stopping || r.checking || r.consumed || r.failure != nil
				if !deny && r.keepHold && r.keepReleased != nil {
					wait := r.keepReleased
					r.mu.Unlock()
					<-wait
					continue
				}
				if !deny {
					s, e = r.reserveLocked(c)
				}
				if !deny && e == nil {
					r.wg.Add(1)
				}
				r.mu.Unlock()
				break
			}
			if deny {
				_ = c.Close()
				continue
			}
			if errors.Is(e, ErrCapacity) {
				r.rejectCapacity(c)
				continue
			}
			if e != nil {
				_ = c.Close()
				if errors.Is(e, ErrExhausted) {
					r.fail(e)
				}
				continue
			}
			go func() { defer r.wg.Done(); r.attach(s) }()
		}
	}()
	return nil
}
