package host

import (
	"context"
	"net"

	"github.com/masahitojp/mariamem/internal/snapshot"
)

// Service is the private owner-facing host contract. SQL and management callers
// share the factory while each implementation retains its own execution join.
type Service interface {
	Port() int
	DialContext(context.Context) (net.Conn, error)
	Close(context.Context) error
	CloseWithStopped(context.Context, func(error)) error
	DisconnectState() (int, <-chan struct{}, <-chan struct{}, <-chan struct{})
	SnapshotHeap(context.Context, bool) (*snapshot.Owned, bool, error)
	SnapshotKeep(context.Context) (*snapshot.Owned, error)
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
