package host

import (
	"context"
	"errors"
	"os"

	"github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

func (s *Server) SnapshotHeap(ctx context.Context, rollback bool) (*snapshot.Owned, bool, error) {
	ctx, finish := timing.Begin(ctx, "snapshot_capture")
	defer finish()
	s.mu.Lock()
	if !s.SnapshotCapable() {
		s.mu.Unlock()
		return nil, false, &Rejected{"unsupported", "guest does not support snapshots"}
	}
	if s.closing {
		s.mu.Unlock()
		return nil, false, &Rejected{"closed", "database is closing"}
	}
	if e := s.snapshotPrecondition(rollback); e != nil {
		s.mu.Unlock()
		return nil, false, e
	}
	if e := ctx.Err(); e != nil {
		s.mu.Unlock()
		return nil, false, e
	}
	s.Guest.RequestCapture()
	s.stopAccepting()
	s.mu.Unlock()
	defer os.RemoveAll(s.transfer)
	if e := s.finish(ctx, false); e != nil {
		s.Guest.DiscardCapture()
		return nil, true, e
	}
	image := s.Guest.TakeCapture()
	if image == nil {
		return nil, true, errors.New("missing snapshot capture")
	}
	owned, e := snapshot.OwnHeap(image, s.build)
	return owned, true, e
}
