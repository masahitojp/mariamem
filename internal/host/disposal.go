package host

import (
	"context"
	"os"

	"github.com/masahitojp/mariamem/internal/disposal"
)

// Only call after stopAccepting under s.mu: no worker Add can race with Wait.
func (s *Server) joinWorkers() <-chan struct{} {
	s.workersOnce.Do(func() {
		s.workersDone = make(chan struct{})
		go func() { s.workers.Wait(); close(s.workersDone) }()
	})
	return s.workersDone
}

// A stopped listener or consumed capture is not proof of disposal. Retain one
// owner through execution join, session join and transfer removal. Close and
// explicit Live retries share it; original operation errors remain unchanged.
func (s *Server) disposeAfter(cause error) error {
	s.disposeOnce.Do(func() {
		done := s.joinWorkers()
		s.disposer = disposal.New(func(ctx context.Context) error {
			if err := disposal.Wait(ctx, s.Guest.Done()); err != nil {
				return err
			}
			if err := disposal.Wait(ctx, done); err != nil {
				return err
			}
			return os.RemoveAll(s.transfer)
		})
	})
	if err := s.disposer.Probe(); err != nil {
		return disposal.Retain(cause, err, s.disposer)
	}
	return cause
}
