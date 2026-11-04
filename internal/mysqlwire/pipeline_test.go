package mysqlwire

import (
	"bytes"
	"context"
	"errors"
	"net"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/guest"
)

type pipelineOutcome struct {
	result guest.Result
	err    error
}

func pipelineWork(t *testing.T, w *wire) (chan pipelineOutcome, func(), chan error) {
	t.Helper()
	started := make(chan struct{})
	release := make(chan struct{})
	var once sync.Once
	finish := func() { once.Do(func() { close(release) }) }
	aborted := make(chan error, 1)
	done := make(chan pipelineOutcome, 1)
	go func() {
		r, err := w.monitoredCall(func(ctx context.Context) (guest.Result, error) {
			close(started)
			select {
			case <-release:
				return guest.Result{OK: true}, nil
			case <-ctx.Done():
				return guest.Result{}, ctx.Err()
			}
		}, func(err error) { aborted <- err; finish() })
		done <- pipelineOutcome{r, err}
	}()
	select {
	case <-started:
	case <-time.After(5 * time.Second):
		t.Fatal("guest not started")
	}
	t.Cleanup(finish)
	return done, finish, aborted
}
func pipelineAwait(t *testing.T, done chan pipelineOutcome) pipelineOutcome {
	t.Helper()
	select {
	case r := <-done:
		return r
	case <-time.After(5 * time.Second):
		t.Fatal("monitor/guest not joined")
		return pipelineOutcome{}
	}
}
func pipelineFrame(body []byte) []byte {
	n := len(body)
	return append([]byte{byte(n), byte(n >> 8), byte(n >> 16), 0}, body...)
}
func pipelinePair(t *testing.T) (*wire, net.Conn) {
	t.Helper()
	a, b := net.Pipe()
	t.Cleanup(func() { a.Close(); b.Close() })
	b.SetDeadline(time.Now().Add(5 * time.Second))
	return &wire{conn: a, timeout: 5 * time.Second}, b
}

func TestPipelinePreservesMultipleFramesAndSequence(t *testing.T) {
	w, peer := pipelinePair(t)
	done, finish, aborted := pipelineWork(t, w)
	first := pipelineFrame([]byte{14})
	second := pipelineFrame([]byte{3, 'x'})
	queued := append(bytes.Clone(first), second...)
	if _, err := peer.Write(queued); err != nil {
		t.Fatal(err)
	}
	finish()
	r := pipelineAwait(t, done)
	if r.err != nil || !r.result.OK {
		t.Fatal(r)
	}
	select {
	case err := <-aborted:
		t.Fatal("queued data caused abort", err)
	default:
	}
	if !bytes.Equal(w.readAhead, queued) || cap(w.readAhead) > maxReadAhead {
		t.Fatal("queue bytes/bound changed")
	}
	begins := 0
	w.begin = func() bool { begins++; return true }
	for i, want := range [][]byte{{14}, {3, 'x'}} {
		w.sequence = 0
		body, err := w.read(true)
		if err != nil || !bytes.Equal(body, want) || w.sequence != 1 {
			t.Fatalf("frame%d: %x %v sequence=%d", i, body, err, w.sequence)
		}
	}
	if begins != 2 || len(w.readAhead) != 0 {
		t.Fatal("admission/buffer retirement", begins, len(w.readAhead))
	}
}
func TestPipelinePartialNextFrameIsNotLost(t *testing.T) {
	w, peer := pipelinePair(t)
	done, finish, _ := pipelineWork(t, w)
	frame := pipelineFrame([]byte{3, 'a', 'b'})
	if _, err := peer.Write(frame[:2]); err != nil {
		t.Fatal(err)
	}
	finish()
	if r := pipelineAwait(t, done); r.err != nil {
		t.Fatal(r.err)
	}
	wrote := make(chan error, 1)
	go func() { _, err := peer.Write(frame[2:]); wrote <- err }()
	w.sequence = 0
	body, err := w.read(true)
	if err != nil || !bytes.Equal(body, frame[4:]) {
		t.Fatal(body, err)
	}
	if err := <-wrote; err != nil {
		t.Fatal(err)
	}
}
func TestPipelineDisconnectIsObservedBehindQueuedInput(t *testing.T) {
	for _, full := range []bool{false, true} {
		t.Run(map[bool]string{false: "partial", true: "full"}[full], func(t *testing.T) {
			w, peer := pipelinePair(t)
			if full {
				w.readAhead = make([]byte, maxReadAhead)
			} else {
				w.readAhead = pipelineFrame([]byte{14})
			}
			done, _, aborted := pipelineWork(t, w)
			peer.Close()
			r := pipelineAwait(t, done)
			if r.err == nil {
				t.Fatal("disconnect hidden by pending input")
			}
			select {
			case cause := <-aborted:
				if cause == nil {
					t.Fatal("missing abort cause")
				}
			default:
				t.Fatal("disconnect did not abort guest")
			}
		})
	}
}
func TestPipelineOverflowFailsClosed(t *testing.T) {
	w, peer := pipelinePair(t)
	w.readAhead = make([]byte, maxReadAhead)
	done, _, aborted := pipelineWork(t, w)
	if _, err := peer.Write([]byte{1}); err != nil {
		t.Fatal(err)
	}
	r := pipelineAwait(t, done)
	if !errors.Is(r.err, errReadAheadLimit) {
		t.Fatal("overflow disposition", r.err)
	}
	select {
	case cause := <-aborted:
		if !errors.Is(cause, errReadAheadLimit) {
			t.Fatal(cause)
		}
	default:
		t.Fatal("overflow did not abort guest")
	}
	if len(w.readAhead) != maxReadAhead || cap(w.readAhead) > maxReadAhead {
		t.Fatal("queue grew beyond bound")
	}
}
func TestPipelineReadAheadAllocationIsBounded(t *testing.T) {
	w, peer := pipelinePair(t)
	done, finish, _ := pipelineWork(t, w)
	body := append([]byte{3}, bytes.Repeat([]byte{'x'}, maxCommandPayload-1)...)
	payload := pipelineFrame(body)
	if _, err := peer.Write(payload); err != nil {
		t.Fatal(err)
	}
	finish()
	if r := pipelineAwait(t, done); r.err != nil {
		t.Fatal(r.err)
	}
	if !bytes.Equal(w.readAhead, payload) || cap(w.readAhead) > maxReadAhead {
		t.Fatal("data or allocation bound")
	}
	w.sequence = 0
	got, err := w.read(true)
	if err != nil || !bytes.Equal(got, body) {
		t.Fatal("maximum queued frame changed", len(got), err)
	}
}
func TestPipelineTimeoutJoinsReader(t *testing.T) {
	w, peer := pipelinePair(t)
	w.timeout = 30 * time.Millisecond
	done := make(chan pipelineOutcome, 1)
	aborted := make(chan error, 1)
	go func() {
		r, err := w.monitoredCall(func(ctx context.Context) (guest.Result, error) { <-ctx.Done(); return guest.Result{}, ctx.Err() }, func(err error) { aborted <- err })
		done <- pipelineOutcome{r, err}
	}()
	if r := pipelineAwait(t, done); !errors.Is(r.err, context.DeadlineExceeded) {
		t.Fatal(r.err)
	}
	select {
	case err := <-aborted:
		t.Fatal("completion deadline mistaken for peer disconnect", err)
	default:
	}
	// No old receiver may steal bytes from a following command.
	wrote := make(chan error, 1)
	go func() { _, err := peer.Write(pipelineFrame([]byte{14})); wrote <- err }()
	w.sequence = 0
	body, err := w.read(true)
	if err != nil || !bytes.Equal(body, []byte{14}) {
		t.Fatal(body, err)
	}
	if err := <-wrote; err != nil {
		t.Fatal(err)
	}
}
func TestPipelineQueuedMalformedFrameIsValidated(t *testing.T) {
	w, peer := pipelinePair(t)
	done, finish, _ := pipelineWork(t, w)
	frame := pipelineFrame([]byte{14})
	frame[3] = 9
	if _, err := peer.Write(frame); err != nil {
		t.Fatal(err)
	}
	finish()
	if r := pipelineAwait(t, done); r.err != nil {
		t.Fatal(r.err)
	}
	w.sequence = 0
	if _, err := w.read(true); err == nil {
		t.Fatal("invalid future sequence accepted")
	}
}

func TestPipelineQueuedInputRespectsAdmissionStop(t *testing.T) {
	w, peer := pipelinePair(t)
	done, finish, _ := pipelineWork(t, w)
	if _, err := peer.Write(pipelineFrame([]byte{14})); err != nil {
		t.Fatal(err)
	}
	finish()
	if result := pipelineAwait(t, done); result.err != nil {
		t.Fatal(result.err)
	}
	begins := 0
	w.begin = func() bool { begins++; return false }
	w.sequence = 0
	if _, err := w.read(true); err == nil || err.Error() != "database is stopping" {
		t.Fatal("queued command bypassed stopped admission", err)
	}
	if begins != 1 || w.sequence != 0 {
		t.Fatal("admission/frame advanced", begins, w.sequence)
	}
}
