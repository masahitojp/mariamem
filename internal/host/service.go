package host

import (
	"context"
	"github.com/masahitojp/mariamem/internal/snapshot"
	"net"
)

// Service is the private owner-facing host contract. SQL and management callers
// share the factory while each implementation retains its own execution join.
type Service interface {
	Port() int
	DialContext(context.Context) (net.Conn, error)
	Close(context.Context) error
	SnapshotHeap(context.Context, bool) (*snapshot.Owned, bool, error)
	Snapshot(context.Context, string, bool) (bool, error)
	Active() int
	Capacity() int
	Busy() bool
	Failure() error
	Done() <-chan struct{}
	RuntimePID() int
	SnapshotCapable() bool
	DisposalComplete() bool
	CaptureDebt() error
}

func (s *Server) Done() <-chan struct{} { return s.Guest.Done() }
func (s *Server) RuntimePID() int       { return s.Guest.PID() }
func (s *Server) CaptureDebt() error    { return nil }

var _ Service = (*Server)(nil)
