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
	ready := make(chan response, 1)
	p := &Process{startupTiming: timing.Enabled(ctx), in: in, out: out, writes: make(chan struct{}, 1), done: make(chan struct{}), pending: map[uint32]chan response{0: ready}}
	timing.Mark(ctx, "linked_execution_begin")
	execution := generatedgo.StartInstance(ctx, childIn, childOut, logs, transfer, restore, timing.Enabled(ctx))
	readDone := make(chan struct{})
	go func() { defer close(readDone); p.read() }()
	go func() {
		err := <-execution
		childIn.Close()
		childOut.Close()
		<-readDone
		// The host response reader is owned by this linked execution, not by
		// the lifetime of a retained Process/Database handle. Join its reader
		// before closing it, and release the FD before publishing completion.
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
