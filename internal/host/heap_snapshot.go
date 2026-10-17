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
	image, takeErr := s.Guest.TakeRoot(s.build)
	if takeErr != nil {
		return nil, true, takeErr
	}
	if image == nil {
		return nil, true, errors.New("missing snapshot capture")
	}

	owned, e := snapshot.OwnRoot(image, s.build)
	for key, v := range image.Counts() {
		timing.Work(ctx, "root/"+key+"/read", v.Read, 0)
		timing.Work(ctx, "root/"+key+"/copy", v.Copy, 0)
		timing.Work(ctx, "root/"+key+"/hash", v.Hash, 0)
		timing.Work(ctx, "root/"+key+"/zero", v.Zero, v.Metadata)
	}
	return owned, true, e
}
