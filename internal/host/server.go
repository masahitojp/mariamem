package host

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/masahitojp/mariamem/internal/artifacts"
	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/mysqlwire"
	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/runtimekind"
	"github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

type Server struct {
	Guest             *guest.Process
	listener          net.Listener
	mu                sync.Mutex
	clients           map[net.Conn]*session
	disconnectChanged chan struct{}
	slots             []bool
	closing           bool
	workers           sync.WaitGroup
	workersOnce       sync.Once
	workersDone       chan struct{}
	disposeOnce       sync.Once
	disposer          *disposal.Owner
	queryTimeout      time.Duration
	transfer          string
	build             string
}

type session struct {
	busy   bool
	status uint16
	slot   uint32
}
type Rejected struct {
	Code    string
	Message string
}

func (e *Rejected) Error() string { return e.Message }

// StartGenerated uses compiled guest identity and the same snapshot/transport contract.
func StartGenerated(ctx context.Context, restore *snapshot.Owned, timeout time.Duration, stderr interface{ Write([]byte) (int, error) }) (*Server, error) {
	if err := artifacts.ValidatePlatform(ctx); err != nil {
		return nil, err
	}
	return start(ctx, restore, timeout, stderr)
}

func start(ctx context.Context, restore *snapshot.Owned, timeout time.Duration, stderr interface{ Write([]byte) (int, error) }) (server *Server, err error) {
	ctx, finishTiming := timing.Begin(ctx, "startup")
	defer finishTiming()
	defer func() {
		if err != nil {
			var detail *diagnostic.Error
			if !errors.As(err, &detail) {
				err = diagnostic.Wrap("host_start", "host_setup", err)
			}
		}
	}()
	build := runtimekind.GuestSHA256
	timing.Mark(ctx, "native_identity_checked")
	var entries []prepared.Entry
	if restore != nil {
		var release func()
		entries, release, err = restore.Acquire(build)
		if err != nil {
			return nil, err
		}
		defer func() {
			if err == nil {
				release()
				return
			}
			// A failed startup may still be reading borrowed restore entries.
			// Keep backing protection until the retained cleanup has joined.
			err = disposal.After(err, func() error { release(); return nil })
		}()
	}
	timing.Mark(ctx, "metadata_snapshot_validated")
	transfer, err := os.MkdirTemp("", "mariamem-transfer-")
	if err != nil {
		return nil, err
	}
	timing.Mark(ctx, "transfer_prepared")
	p, err := guest.StartGenerated(ctx, transfer, entries, stderr)
	if err != nil {
		return nil, disposal.RemoveAfter(err, transfer)
	}
	if restore != nil && p.SnapshotVersion != 1 {
		return nil, disposal.RemoveAfter(p.AbortAndWait(fmt.Errorf("guest does not support snapshot restore")), transfer)
	}
	timing.Mark(ctx, "guest_ready")
	ln, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return nil, diagnostic.Wrap("host_start", "host_listen", disposal.RemoveAfter(p.AbortAndWait(err), transfer))
	}
	s := &Server{Guest: p, listener: ln, clients: make(map[net.Conn]*session), slots: make([]bool, p.MaxSessions), queryTimeout: timeout, transfer: transfer, build: build}
	timing.Mark(ctx, "wire_listener_ready")
	timing.ReadGuest(ctx, transfer)
	timing.Mark(ctx, "guest_timing_read")
	go s.accept()
	return s, nil
}
func (s *Server) Port() int     { return s.listener.Addr().(*net.TCPAddr).Port }
func (s *Server) Closing() bool { s.mu.Lock(); defer s.mu.Unlock(); return s.closing }
func (s *Server) Active() int   { s.mu.Lock(); defer s.mu.Unlock(); return len(s.clients) }

// DisconnectState samples the count and registers its change notification under
// one lock, so a disconnect between sampling and waiting cannot be lost.
// Notifications only prompt a recheck; none establishes completed disposal.
func (s *Server) DisconnectState() (active int, changed, failed, done <-chan struct{}) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.disconnectChanged == nil {
		s.disconnectChanged = make(chan struct{})
	}
	return len(s.clients), s.disconnectChanged, s.Guest.FailureDone(), s.Guest.Done()
}

// notifyDisconnectLocked broadcasts to all waiters without a goroutine per
// waiter. Allocate the next generation only when another observer needs it.
func (s *Server) notifyDisconnectLocked() {
	if s.disconnectChanged != nil {
		close(s.disconnectChanged)
		s.disconnectChanged = nil
	}
}

func (s *Server) Capacity() int  { return len(s.slots) }
func (s *Server) Failure() error { return s.Guest.Err() }
func (s *Server) Busy() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, c := range s.clients {
		if c.busy {
			return true
		}
	}
	return false
}
func (s *Server) SnapshotCapable() bool { return s.Guest.SnapshotVersion == 1 && s.build != "" }
func (s *Server) accept() {
	for {
		conn, err := s.listener.Accept()
		if err != nil {
			return
		}
		if err := s.attach(conn); err != nil {
			var rejected *Rejected
			if errors.As(err, &rejected) && rejected.Code == "capacity" {
				mysqlwire.RejectCapacity(conn)
			} else if errors.As(err, &rejected) && rejected.Code == "unusable" {
				mysqlwire.RejectUnavailable(conn)
			} else {
				conn.Close()
				return
			}
		}
	}
}

// DialContext connects to this server without a TCP socket. Rejected dials
// return before starting any worker; successful dials share TCP admission.
func (s *Server) DialContext(ctx context.Context) (net.Conn, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	client, server := net.Pipe()
	if err := s.attach(server); err != nil {
		client.Close()
		server.Close()
		return nil, err
	}
	return client, nil
}

// attach reserves a guest slot and joins shutdown under the same lock.
// The caller owns rejected connections and must close them or send a wire error.
func (s *Server) attach(conn net.Conn) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closing {
		return &Rejected{"closed", "database is closing"}
	}
	if cause := s.Guest.Err(); cause != nil {
		return errors.Join(&Rejected{"unusable", "database instance terminated"}, cause)
	}
	slot, ok := s.allocateSlotLocked()
	if !ok {
		return &Rejected{"capacity", "mariamem session capacity exhausted"}
	}
	state := &session{busy: true, slot: slot}
	s.clients[conn] = state
	s.workers.Add(1)
	go func() {
		defer s.workers.Done()
		defer conn.Close()
		defer func() {
			s.mu.Lock()
			defer s.mu.Unlock()
			delete(s.clients, conn)
			s.slots[state.slot] = false
			s.notifyDisconnectLocked()
		}()
		activity := mysqlwire.Activity{
			Begin: func() bool {
				s.mu.Lock()
				defer s.mu.Unlock()
				if s.closing {
					return false
				}
				state.busy = true
				return true
			},
			Idle:    func(status uint16) { s.mu.Lock(); defer s.mu.Unlock(); state.status = status; state.busy = false },
			Cleanup: func() { s.mu.Lock(); defer s.mu.Unlock(); state.busy = true },
		}
		if err := mysqlwire.Serve(conn, s.Guest, state.slot, s.queryTimeout, s.Closing, activity); err != nil {
			s.Guest.Abort(fmt.Errorf("SQL session: %w", err))
		}
		// Serve acknowledges guest close; abort precedes releasing a failed slot.
	}()
	return nil
}

// allocateSlotLocked reserves the lowest free guest slot before session open.
func (s *Server) allocateSlotLocked() (uint32, bool) {
	for i, occupied := range s.slots {
		if !occupied {
			s.slots[i] = true
			return uint32(i), true
		}
	}
	return 0, false
}
func (s *Server) Close(ctx context.Context) (err error) {
	defer func() { err = s.disposeAfter(err) }()
	s.mu.Lock()
	s.stopAccepting()
	s.mu.Unlock()
	return s.finish(ctx, false)
}

// stopAccepting requires mu. The same lock gates handshake/query admission.
func (s *Server) stopAccepting() {
	s.closing = true
	s.notifyDisconnectLocked()
	s.listener.Close()
	for conn := range s.clients {
		conn.Close()
	}
}
func (s *Server) Snapshot(ctx context.Context, destination string, rollback bool) (closed bool, err error) {
	ctx, finishTiming := timing.Begin(ctx, "snapshot")
	defer finishTiming()
	s.mu.Lock()
	if !s.SnapshotCapable() {
		s.mu.Unlock()
		return false, &Rejected{"unsupported", "guest does not support snapshots"}
	}
	if s.closing {
		s.mu.Unlock()
		return false, &Rejected{"closed", "database is closing"}
	}
	if rejected := s.snapshotPrecondition(rollback); rejected != nil {
		s.mu.Unlock()
		return false, rejected
	}
	if destination == "" {
		s.mu.Unlock()
		return false, &Rejected{"destination", "snapshot destination is required"}
	}
	path, err := filepath.Abs(destination)
	if err == nil {
		err = os.Mkdir(path, 0700)
	}
	if err != nil {
		s.mu.Unlock()
		return false, &Rejected{"destination", err.Error()}
	}
	// Only this call owns the destination after Mkdir succeeds. Existing paths
	// return above, before this cleanup is registered.
	defer func() {
		if err != nil {
			err = disposal.RemoveAfter(err, path)
		}
	}()
	timing.Mark(ctx, "preconditions_destination_ready")
	s.stopAccepting()
	s.mu.Unlock()
	defer func() { err = s.disposeAfter(err) }()
	if err = s.finish(ctx, true); err != nil {
		return true, err
	}
	timing.Mark(ctx, "guest_stopped")
	err = snapshot.PublishContext(ctx, s.transfer, path, s.build)
	timing.Mark(ctx, "snapshot_published")
	return true, err
}
func (s *Server) finish(ctx context.Context, export bool) error {
	done := s.joinWorkers()
	var err error
	select {
	case <-done:
		if export {
			timing.Mark(ctx, "sessions_drained")
			err = s.Guest.Export(ctx)
			timing.Mark(ctx, "export_acknowledged")
		} else {
			err = s.Guest.Shutdown(ctx)
		}
	case <-ctx.Done():
		err = ctx.Err()
		s.Guest.Abort(err)
	}
	if err != nil {
		s.Guest.Abort(err)
	}
	s.mu.Lock()
	for conn := range s.clients {
		conn.Close()
	}
	s.mu.Unlock()
	select {
	case <-s.Guest.Done():
	case <-time.After(10 * time.Second):
		return fmt.Errorf("guest cleanup timed out: %w", err)
	}
	select {
	case <-done:
	case <-time.After(10 * time.Second):
		return fmt.Errorf("session cleanup timed out: %w", err)
	}
	return err
}

// snapshotPrecondition requires s.mu; SQL admission uses that same lock.
func (s *Server) snapshotPrecondition(rollback bool) error {
	for _, state := range s.clients {
		if state.busy {

			return &Rejected{"busy", "handshake, query or session cleanup is active"}
		}
		if state.status&1 != 0 && !rollback {

			return &Rejected{"transaction_active", "commit/rollback first, or request rollback"}
		}
	}
	return nil
}
