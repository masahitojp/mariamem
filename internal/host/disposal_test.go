package host

import (
	"context"
	"encoding/binary"
	"errors"
	"io"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
	"github.com/masahitojp/mariamem/internal/guest"
)

func TestConsumedFailureKeepsTransferUntilGuestAndWorkersJoin(t *testing.T) {
	childIn, in := io.Pipe()
	out, childOut := io.Pipe()
	completed := make(chan error, 1)
	defer childIn.Close()
	defer childOut.Close()
	defer func() {
		select {
		case completed <- nil:
		default:
		}
	}()
	go func() {
		body := []byte(`{"request_id":0,"result":{"ready":true,"api_version":2,"max_sessions":16}}`)
		_ = binary.Write(childOut, binary.LittleEndian, uint32(len(body)))
		_, _ = childOut.Write(body)
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	p, err := guest.Connect(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	transfer := filepath.Join(t.TempDir(), "transfer")
	if err := os.Mkdir(transfer, 0700); err != nil {
		t.Fatal(err)
	}
	s := &Server{Guest: p, listener: unusedListener{}, transfer: transfer}
	s.workers.Add(1)
	var release sync.Once
	defer release.Do(s.workers.Done)
	s.mu.Lock()
	s.stopAccepting()
	s.mu.Unlock()
	cause := errors.New("capture consumed but execution not joined")
	err = s.disposeAfter(cause)
	owners := disposal.Owners(err)
	if len(owners) != 1 || owners[0].Complete() {
		t.Fatal("lost cleanup owner", err)
	}
	if _, e := os.Stat(transfer); e != nil {
		t.Fatal("removed before guest join", e)
	}
	completed <- nil
	select {
	case <-p.Done():
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	if owners[0].Complete() {
		t.Fatal("disposed before worker join")
	}
	if _, e := os.Stat(transfer); e != nil {
		t.Fatal("removed before worker join", e)
	}
	release.Do(s.workers.Done)
	if e := disposal.Retry(ctx, err); e != nil {
		t.Fatal(e)
	}
	if _, e := os.Stat(transfer); !os.IsNotExist(e) {
		t.Fatal("retained joined transfer", e)
	}
	if !errors.Is(err, cause) {
		t.Fatal("original cause lost")
	}
	if again := s.disposeAfter(cause); again != cause {
		t.Fatal("cleanup state not reused", again)
	}
}

// Completion of a runtime attempt is not proof that its resources were freed.
func TestRuntimeCleanupDebtRetainsDisposal(t *testing.T) {
	childIn, in := io.Pipe()
	out, childOut := io.Pipe()
	completed := make(chan error, 1)
	go func() {
		body := []byte(`{"request_id":0,"result":{"ready":true,"api_version":2,"max_sessions":16}}`)
		binary.Write(childOut, binary.LittleEndian, uint32(len(body)))
		childOut.Write(body)
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	p, err := guest.Connect(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	var gate sync.Mutex
	released := false
	failure := errors.New("injected unmap failure")
	runtimeOwner := disposal.New(func(context.Context) error {
		gate.Lock()
		defer gate.Unlock()
		if !released {
			return failure
		}
		return nil
	})
	debt := disposal.Retain(errors.New("original runtime failure"), failure, runtimeOwner)
	completed <- debt
	<-p.Done()
	transfer := filepath.Join(t.TempDir(), "transfer")
	os.Mkdir(transfer, 0700)
	s := &Server{Guest: p, listener: unusedListener{}, transfer: transfer}
	s.mu.Lock()
	s.stopAccepting()
	s.mu.Unlock()
	pool, _ := forklimit.New(1)
	lease, _ := pool.Acquire(ctx)
	if err := lease.Activate(); err != nil {
		t.Fatal(err)
	}
	result := s.disposeAfter(debt)
	lease.TrackCleanup(result)
	if _, occupied := pool.Usage(); occupied != 1 {
		t.Fatal("returned unresolved lease")
	}
	if s.DisposalComplete() {
		t.Fatal("failed runtime release reported disposed")
	}
	if _, err := os.Stat(transfer); err != nil {
		t.Fatal("removed before runtime release", err)
	}
	gate.Lock()
	released = true
	gate.Unlock()
	if err := disposal.Retry(ctx, result); err != nil {
		t.Fatal(err)
	}
	if !s.DisposalComplete() {
		t.Fatal("retry did not confirm disposal")
	}
	for {
		_, occupied := pool.Usage()
		if occupied == 0 {
			break
		}
		select {
		case <-ctx.Done():
			t.Fatal("lease not returned", ctx.Err())
		default:
			time.Sleep(time.Millisecond)
		}
	}
	if !errors.Is(result, failure) {
		t.Fatal("lost original failure")
	}
}
