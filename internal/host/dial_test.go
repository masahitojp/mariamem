package host

import (
	"context"
	"errors"
	"net"
	"sync"
	"testing"

	"github.com/masahitojp/mariamem/internal/guest"
)

func TestRejectedPipeDialsDoNotStartWorkers(t *testing.T) {
	s := &Server{Guest: &guest.Process{}, slots: []bool{true, true}, clients: make(map[net.Conn]*session)}
	var wg sync.WaitGroup
	for range 32 {
		wg.Go(func() {
			for range 64 {
				c, e := s.DialContext(context.Background())
				var rejected *Rejected
				if c != nil || !errors.As(e, &rejected) || rejected.Code != "capacity" {
					t.Errorf("%v %v", c, e)
					if c != nil {
						c.Close()
					}
				}
			}
		})
	}
	wg.Wait()
	if s.Active() != 0 {
		t.Fatal("rejected dials registered clients")
	}
	s.workers.Wait()
	s.mu.Lock()
	s.closing = true
	s.mu.Unlock()
	if c, e := s.DialContext(context.Background()); c != nil || e == nil {
		t.Fatal(c, e)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, e := s.DialContext(ctx); !errors.Is(e, context.Canceled) {
		t.Fatal(e)
	}
}
