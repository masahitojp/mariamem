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

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/mysqlwire"
	"github.com/masahitojp/mariamem/internal/snapshot"
)

type Server struct {
	Guest        *guest.Process
	listener     net.Listener
	mu           sync.Mutex
	clients      map[net.Conn]*session
	slots        []bool
	closing      bool
	workers      sync.WaitGroup
	queryTimeout time.Duration
	transfer     string
	build        string
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

func Start(ctx context.Context, runtime, module, wasmerDir, restore string, timeout time.Duration, stderr interface{ Write([]byte) (int, error) }) (server *Server, err error) {
	defer func() {
		if err != nil {
			var detail *diagnostic.Error
			if !errors.As(err, &detail) {
				err = diagnostic.Wrap("host_start", "host_setup", err)
			}
		}
	}()
	build, metadataErr := snapshot.ModuleBuild(module)
	if metadataErr != nil && !os.IsNotExist(metadataErr) {
		return nil, diagnostic.Wrap("artifact_mismatch", "artifact_validation", metadataErr)
	}
	if restore != "" {
		if metadataErr != nil {
			return nil, diagnostic.Wrap("artifact_mismatch", "artifact_validation", metadataErr)
		}
		var err error
		restore, err = filepath.Abs(restore)
		if err != nil {
			return nil, err
		}
		if _, err = snapshot.Validate(restore, build); err != nil {
			return nil, err
		}
	}
	transfer, err := os.MkdirTemp("", "mariamem-transfer-")
	if err != nil {
		return nil, err
	}
	p, err := guest.Start(ctx, runtime, module, wasmerDir, transfer, restore, stderr)
	if err != nil {
		os.RemoveAll(transfer)
		return nil, err
	}
	if p.SnapshotVersion == 1 && build == "" {
		os.RemoveAll(transfer)
		return nil, p.AbortAndWait(fmt.Errorf("snapshot guest requires valid artifact metadata: %w", metadataErr))
	}
	if restore != "" && p.SnapshotVersion != 1 {
		os.RemoveAll(transfer)
		return nil, p.AbortAndWait(fmt.Errorf("guest does not support snapshot restore"))
	}
	ln, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		os.RemoveAll(transfer)
		return nil, diagnostic.Wrap("host_start", "host_listen", p.AbortAndWait(err))
	}
	s := &Server{Guest: p, listener: ln, clients: make(map[net.Conn]*session), slots: make([]bool, p.MaxSessions), queryTimeout: timeout, transfer: transfer, build: build}
	go s.accept()
	return s, nil
}
func (s *Server) Port() int      { return s.listener.Addr().(*net.TCPAddr).Port }
func (s *Server) Closing() bool  { s.mu.Lock(); defer s.mu.Unlock(); return s.closing }
func (s *Server) Active() int    { s.mu.Lock(); defer s.mu.Unlock(); return len(s.clients) }
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
		s.mu.Lock()
		if s.closing {
			s.mu.Unlock()
			conn.Close()
			return
		}
		if s.Guest.Err() != nil {
			s.mu.Unlock()
			mysqlwire.RejectUnavailable(conn)
			continue
		}
		slot, ok := s.allocateSlotLocked()
		if !ok {
			s.mu.Unlock()
			mysqlwire.RejectCapacity(conn)
			continue
		}
		state := &session{busy: true, slot: slot}
		s.clients[conn] = state
		s.workers.Add(1)
		s.mu.Unlock()
		go func() {
			defer s.workers.Done()
			defer conn.Close()
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
			err := mysqlwire.Serve(conn, s.Guest, state.slot, s.queryTimeout, s.Closing, activity)
			if err != nil {
				s.Guest.Abort(fmt.Errorf("SQL session: %w", err))
			}
			s.mu.Lock()
			delete(s.clients, conn)
			// Serve waits for the guest's close acknowledgement. On failure the
			// guest is aborted before a slot can be offered to another client.
			s.slots[state.slot] = false
			s.mu.Unlock()
		}()
	}
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
	defer func() { err = errors.Join(err, os.RemoveAll(s.transfer)) }()
	s.mu.Lock()
	s.stopAccepting()
	s.mu.Unlock()
	return s.finish(ctx, false)
}

// stopAccepting requires mu. The same lock gates handshake/query admission.
func (s *Server) stopAccepting() {
	s.closing = true
	s.listener.Close()
	for conn := range s.clients {
		conn.Close()
	}
}
func (s *Server) Snapshot(ctx context.Context, destination string, rollback bool) (closed bool, err error) {
	s.mu.Lock()
	if !s.SnapshotCapable() {
		s.mu.Unlock()
		return false, &Rejected{"unsupported", "guest does not support snapshots"}
	}
	if s.closing {
		s.mu.Unlock()
		return false, &Rejected{"closed", "database is closing"}
	}
	for _, state := range s.clients {
		if state.busy {
			s.mu.Unlock()
			return false, &Rejected{"busy", "handshake, query or session cleanup is active"}
		}
		if state.status&1 != 0 && !rollback {
			s.mu.Unlock()
			return false, &Rejected{"transaction_active", "commit/rollback first, or request rollback"}
		}
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
			if cleanupErr := os.RemoveAll(path); cleanupErr != nil {
				err = errors.Join(err, fmt.Errorf("remove partial snapshot: %w", cleanupErr))
			}
		}
	}()
	s.stopAccepting()
	s.mu.Unlock()
	defer os.RemoveAll(s.transfer)
	if err = s.finish(ctx, true); err != nil {
		return true, err
	}
	return true, snapshot.Publish(s.transfer, path, s.build)
}
func (s *Server) finish(ctx context.Context, export bool) error {
	done := make(chan struct{})
	go func() { s.workers.Wait(); close(done) }()
	var err error
	select {
	case <-done:
		if export {
			err = s.Guest.Export(ctx)
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
