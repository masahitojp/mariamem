package guest

import (
	"context"
	"errors"
	"fmt"
	"io"
	"time"

	"github.com/masahitojp/mariamem/internal/generatedgo"
	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/preparedproto"
	"github.com/masahitojp/mariamem/internal/timing"
)

func startLinked(ctx context.Context, module, transfer string, restore []prepared.Entry, stderr io.Writer) (*Process, error) {
	if module != generatedgo.GuestSHA256 {
		return nil, fmt.Errorf("compiled guest identity mismatch")
	}
	tail := &stderrTail{}
	logs := io.Writer(tail)
	if stderr != nil {
		logs = io.MultiWriter(stderr, tail)
	}
	childIn, in := newBytePipe()
	out, childOut := newBytePipe()
	timing.Mark(ctx, "linked_execution_begin")
	capture := &prepared.Capture{}
	failed := make(chan error, 1)
	stopped, execution := generatedgo.StartInstanceWithStopped(childIn, childOut, logs, transfer, restore, timing.Enabled(ctx), func(err error) { failed <- err }, capture)
	p, e := ConnectWithStopped(ctx, in, out, execution, func() {
		childIn.Close()
		childOut.Close()
	}, tail, failed, stopped)
	if p != nil {
		p.capture = capture
	}
	return p, e
}

// Connect owns a framed transport, not a runtime executable. Completion must
// be followed by closePeer closing the peer endpoints (or already-closed peers). The linked runtime and deterministic
// transport fixtures use the same response reader and cooperative teardown.
func Connect(ctx context.Context, in io.WriteCloser, out io.ReadCloser, completed <-chan error, closePeer func(), logs io.Writer) (*Process, error) {
	return ConnectWithFailure(ctx, in, out, completed, closePeer, logs, nil)
}

// ConnectWithFailure poisons the instance on an early fatal runtime notification.
// completed remains a separate joined-cleanup boundary, including after failure.
func ConnectWithFailure(ctx context.Context, in io.WriteCloser, out io.ReadCloser, completed <-chan error, closePeer func(), logs io.Writer, failed <-chan error) (*Process, error) {
	return connectWithFailure(ctx, in, out, completed, closePeer, logs, failed, 10*time.Second)
}

// ConnectWithStopped shares the production lifecycle adapter with controlled
// transports. stopped must report once before completed, after final guest I/O.
func ConnectWithStopped(ctx context.Context, in io.WriteCloser, out io.ReadCloser, completed <-chan error, closePeer func(), logs io.Writer, failed <-chan error, stopped <-chan error) (*Process, error) {
	return connectLifecycle(ctx, in, out, completed, closePeer, logs, failed, stopped, 10*time.Second)
}

func connectWithFailure(ctx context.Context, in io.WriteCloser, out io.ReadCloser, completed <-chan error, closePeer func(), logs io.Writer, failed <-chan error, grace time.Duration) (*Process, error) {
	return connectLifecycle(ctx, in, out, completed, closePeer, logs, failed, nil, grace)
}

func connectLifecycle(ctx context.Context, in io.WriteCloser, out io.ReadCloser, completed <-chan error, closePeer func(), logs io.Writer, failed <-chan error, runtimeStopped <-chan error, grace time.Duration) (*Process, error) {
	tail, ok := logs.(*stderrTail)
	if !ok {
		tail = &stderrTail{}
	}
	ready := make(chan response, 1)
	p := &Process{startupTiming: timing.Enabled(ctx), in: in, out: out, writes: make(chan struct{}, 1), done: make(chan struct{}), stopped: make(chan struct{}), pending: map[uint32]chan response{0: ready}}
	readDone := make(chan struct{})
	go func() { defer close(readDone); p.read() }()
	go func() {
		retired := false
		retire := func(stopErr error) {
			if retired {
				return
			}
			retired = true
			p.mu.Lock()
			p.stopping = true
			p.mu.Unlock()
			if stopErr != nil {
				p.Abort(stopErr)
			}
			p.closeInput()
			if closePeer != nil {
				closePeer()
			}
			<-readDone
			p.closeOutput()
			p.stopErr = stopErr
			close(p.stopped)
		}
		var exitErr error
		for {
			select {
			case stopErr := <-runtimeStopped:
				retire(stopErr)
				runtimeStopped = nil
			case err := <-failed:
				p.Abort(err)
				failed = nil
			case exitErr = <-completed:
				if !retired {
					stopErr := exitErr
					if runtimeStopped != nil {
						stopErr = <-runtimeStopped
					}
					retire(stopErr)
				}
				if exitErr != nil {
					p.Abort(exitErr)
				}
				p.exitErr = exitErr
				close(p.done)
				p.fail(errors.New("guest exited"))
				return
			}
		}
	}()
	select {
	case r := <-ready:
		timing.MarkAt(ctx, "ready_header_received", r.headerAt)
		timing.MarkAt(ctx, "ready_frame_decoded", r.decodedAt)
		timing.Mark(ctx, "ready_response_observed")
		if r.err == nil && r.result.Ready && r.result.Version == 2 && r.result.MaxSessions > 0 && r.result.MaxSessions <= 65536 {
			p.SnapshotVersion = r.result.SnapshotVersion
			p.MaxSessions = r.result.MaxSessions
			if r.result.PreparedVersion != 0 && r.result.PreparedVersion != preparedproto.Version {
				return nil, startupError(p.abortAndWait(errors.New("unsupported prepared protocol"), grace), tail)
			}
			p.PreparedVersion = r.result.PreparedVersion
			p.PreparedOperations = append([]uint8(nil), r.result.PreparedOperations...)
			return p, nil
		}
		if r.err == nil {
			r.err = errors.New("unsupported guest: requires multi-session API v2 with valid capacity")
		}
		return nil, startupError(p.abortAndWait(r.err, grace), tail)
	case <-ctx.Done():
		return nil, startupError(p.abortAndWait(ctx.Err(), grace), tail)
	}
}
