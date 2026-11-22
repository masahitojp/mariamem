package host

import (
	"context"
	"errors"
	"io"
	"net"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/masahitojp/mariamem/internal/artifacts"
	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/generatedgo"
	"github.com/masahitojp/mariamem/internal/nativewire"
	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/runtimekind"
	"github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

// Rejected is a typed non-fatal precondition rejection surfaced to public callers.
type Rejected struct {
	Code    string
	Message string
}

func (e *Rejected) Error() string { return e.Message }

// StartGenerated starts the compiled generated-Go guest over the B1 native wire contract.
func StartGenerated(ctx context.Context, restore *snapshot.Owned, timeout time.Duration, stderr io.Writer) (Service, error) {
	return StartNativeGenerated(ctx, restore, timeout, stderr)
}

// Native connects one opaque native core to the existing owner service. It owns
// neither a fork pool nor Live generations. Runtime construction stays injected.
type Native struct {
	*nativewire.Backend
	build  string
	debtMu sync.Mutex
	debt   error
}

var _ Service = (*Native)(nil)

func StartNativeGenerated(ctx context.Context, restore *snapshot.Owned, timeout time.Duration, stderr io.Writer) (Service, error) {
	return StartNative(ctx, restore, timeout, stderr, runtimekind.GuestSHA256, func(x nativewire.Execution) <-chan error {
		return generatedgo.StartWireInstance(x.Input, x.Output, x.Stderr, "", x.Restore, false, x.Failure, x.Epoch, &generatedgo.WireLifecycle{
			Capture:   x.Capture,
			Approval:  x.Approval,
			OnStopped: x.Stopped,
		})
	})
}

func StartNative(ctx context.Context, restore *snapshot.Owned, timeout time.Duration, stderr io.Writer, build string, runner nativewire.Runner) (Service, error) {
	if e := artifacts.ValidatePlatform(ctx); e != nil {
		return nil, e
	}
	return startNative(ctx, restore, timeout, stderr, build, runner, func() (net.Listener, error) { return net.Listen("tcp4", "127.0.0.1:0") })
}
func startNative(ctx context.Context, restore *snapshot.Owned, timeout time.Duration, stderr io.Writer, build string, runner nativewire.Runner, listen func() (net.Listener, error)) (Service, error) {
	ctx, finishTiming := timing.Begin(ctx, "startup")
	defer finishTiming()
	var entries []prepared.Entry
	release := func() {}
	if restore != nil {
		var e error
		entries, release, e = restore.Acquire(build)
		if e != nil {
			return nil, e
		}
	}
	b, e := nativewire.Start(ctx, nativewire.Config{Runner: runner, Build: build, Restore: entries, QueryTimeout: timeout, Stderr: stderr, RejectCapacity: RejectCapacity})
	if e != nil {
		return nil, disposal.After(e, func() error { release(); return nil })
	}
	release() // READY follows the runtime's owned prepared mapping acquisition.
	timing.Mark(ctx, "guest_ready")
	s := &Native{Backend: b, build: build}
	l, e := listen()
	if e == nil {
		e = b.Serve(l)
	}
	if e == nil {
		timing.Mark(ctx, "wire_listener_ready")
		e = ctx.Err()
	}
	if e != nil {
		probe, cancel := context.WithCancel(context.Background())
		cancel()
		return nil, errors.Join(e, s.Close(probe))
	}
	return s, nil
}
func (s *Native) RuntimePID() int { return os.Getpid() }
func nativeRejection(e error) error {
	if e == nil {
		return nil
	}
	var rejected *nativewire.Rejected
	if errors.As(e, &rejected) {
		return errors.Join(&Rejected{rejected.Code, rejected.Message}, e)
	}
	code := ""
	switch {
	case errors.Is(e, nativewire.ErrCapacity):
		code = "capacity"
	case errors.Is(e, nativewire.ErrBusy):
		code = "busy"
	case errors.Is(e, nativewire.ErrClosed):
		code = "closed"
	}
	if code != "" {
		return errors.Join(&Rejected{code, e.Error()}, e)
	}
	return e
}
func (s *Native) DialContext(ctx context.Context) (net.Conn, error) {
	c, e := s.Backend.DialContext(ctx)
	return c, nativeRejection(e)
}
func (s *Native) SnapshotHeap(ctx context.Context, rollback bool) (*snapshot.Owned, bool, error) {
	o, c, e := s.Backend.SnapshotHeap(ctx, rollback)
	return o, c, nativeRejection(e)
}
func (s *Native) SnapshotKeep(ctx context.Context) (*snapshot.Owned, error) {
	o, e := s.Backend.SnapshotKeep(ctx)
	return o, nativeRejection(e)
}
func (s *Native) CaptureDebt() error {
	s.debtMu.Lock()
	defer s.debtMu.Unlock()
	return errors.Join(s.debt, s.Backend.CaptureDebt())
}

// Snapshot retains the existing standalone-host cold-directory format. Claim a
// fresh destination before consuming the source; never remove a caller's path.
func (s *Native) Snapshot(ctx context.Context, destination string, rollback bool) (consumed bool, err error) {
	if e := ctx.Err(); e != nil {
		return false, e
	}
	if destination == "" {
		return false, &Rejected{"destination", "snapshot destination is required"}
	}
	path, e := filepath.Abs(destination)
	if e == nil {
		e = os.Mkdir(path, 0700)
	}
	if e != nil {
		return false, &Rejected{"destination", e.Error()}
	}
	defer func() {
		if err != nil {
			err = disposal.RemoveAfter(err, path)
		}
	}()
	owned, consumed, err := s.SnapshotHeap(ctx, rollback)
	if owned == nil {
		return consumed, err
	}
	defer func() {
		cleanup := owned.Close()
		if cleanup != nil {
			s.debtMu.Lock()
			s.debt = errors.Join(s.debt, cleanup)
			s.debtMu.Unlock()
			cleanup = disposal.After(cleanup, owned.Close)
		}
		err = errors.Join(err, cleanup)
	}()
	if err != nil {
		return consumed, err
	}
	transfer, e := os.MkdirTemp(filepath.Dir(path), ".mariamem-native-export-")
	if e != nil {
		return consumed, e
	}
	defer func() { err = disposal.RemoveAfter(err, transfer) }()
	image := filepath.Join(transfer, "image")
	if err = owned.Handoff(image, s.build); err == nil {
		err = snapshot.PublishContext(ctx, image, path, s.build)
	}
	return consumed, err
}
