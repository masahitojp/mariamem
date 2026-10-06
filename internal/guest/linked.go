package guest

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"

	"github.com/masahitojp/mariamem/internal/generatedgo"
	"github.com/masahitojp/mariamem/internal/timing"
)

func startLinked(ctx context.Context, module, transfer, restore string, stderr io.Writer) (*Process, error) {
	if module != generatedgo.GuestSHA256 {
		return nil, fmt.Errorf("compiled guest identity mismatch")
	}
	tail := &stderrTail{}
	logs := io.Writer(tail)
	if stderr != nil {
		logs = io.MultiWriter(stderr, tail)
	}
	childIn, in, err := os.Pipe()
	if err != nil {
		return nil, err
	}
	out, childOut, err := os.Pipe()
	if err != nil {
		childIn.Close()
		in.Close()
		return nil, err
	}
	timing.Mark(ctx, "linked_execution_begin")
	execution := generatedgo.StartInstance(childIn, childOut, logs, transfer, restore, timing.Enabled(ctx))
	return Connect(ctx, in, out, execution, func() {
		childIn.Close()
		childOut.Close()
	}, tail)
}

// Connect owns a framed transport, not a runtime executable. Completion must
// be followed by closePeer closing the peer endpoints (or already-closed peers). The linked runtime and deterministic
// transport fixtures use the same response reader and cooperative teardown.
func Connect(ctx context.Context, in io.WriteCloser, out io.ReadCloser, completed <-chan error, closePeer func(), logs io.Writer) (*Process, error) {
	tail, ok := logs.(*stderrTail)
	if !ok {
		tail = &stderrTail{}
	}
	ready := make(chan response, 1)
	p := &Process{startupTiming: timing.Enabled(ctx), in: in, out: out, writes: make(chan struct{}, 1), done: make(chan struct{}), pending: map[uint32]chan response{0: ready}}
	readDone := make(chan struct{})
	go func() { defer close(readDone); p.read() }()
	go func() {
		err := <-completed
		if closePeer != nil {
			closePeer()
		}
		<-readDone
		_ = out.Close()
		p.exitErr = err
		close(p.done)
		p.fail(errors.New("guest exited"))
	}()
	select {
	case r := <-ready:
		timing.MarkAt(ctx, "ready_header_received", r.headerAt)
		timing.MarkAt(ctx, "ready_frame_decoded", r.decodedAt)
		timing.Mark(ctx, "ready_response_observed")
		if r.err == nil && r.result.Ready && r.result.Version == 2 && r.result.MaxSessions > 0 && r.result.MaxSessions <= 65536 {
			p.SnapshotVersion = r.result.SnapshotVersion
			p.MaxSessions = r.result.MaxSessions
			return p, nil
		}
		if r.err == nil {
			r.err = errors.New("unsupported guest: requires multi-session API v2 with valid capacity")
		}
		return nil, startupError(p.AbortAndWait(r.err), tail)
	case <-ctx.Done():
		return nil, startupError(p.AbortAndWait(ctx.Err()), tail)
	}
}
