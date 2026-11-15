package guest

import (
	"context"
	"errors"
	"io"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
)

func TestFailedGreetingRetainsLateJoinedOwnerWithNilProcess(t *testing.T) {
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
	go func() { _, _ = childOut.Write([]byte{0, 0, 0, 0}) }()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	p, err := connectWithFailure(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, io.Discard, nil, time.Millisecond)
	if p != nil {
		t.Fatal("failed startup became a usable Process")
	}
	var detail *diagnostic.Error
	if !errors.As(err, &detail) || detail.Code != "guest_connection" || detail.Stage != "guest_ready" || !strings.Contains(err.Error(), "invalid guest frame") {
		t.Fatal("lost original diagnostics", err)
	}
	owners := disposal.Owners(err)
	if len(owners) != 1 || owners[0].Complete() {
		t.Fatal("lost unjoined Process", err)
	}
	probe, stop := context.WithCancel(context.Background())
	stop()
	if e := disposal.Retry(probe, err); !errors.Is(e, context.Canceled) {
		t.Fatal(e)
	}
	completed <- nil
	if e := disposal.Retry(ctx, err); e != nil {
		t.Fatal(e)
	}
	if !owners[0].Complete() || !strings.Contains(err.Error(), "invalid guest frame") {
		t.Fatal("rewrote failed startup")
	}
}

// A late completed notification may still carry unresolved runtime resources.
// The failed-startup owner must not release its Fork reservation on Done alone.
func TestFailedGreetingRetainsLateReleaseDebt(t *testing.T) {
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
	go func() { _, _ = childOut.Write([]byte{0, 0, 0, 0}) }()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	pool, err := forklimit.New(1)
	if err != nil {
		t.Fatal(err)
	}
	lease, err := pool.Acquire(ctx)
	if err != nil {
		t.Fatal(err)
	}
	p, err := connectWithFailure(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, io.Discard, nil, time.Millisecond)
	if p != nil || err == nil {
		t.Fatal("expected failed startup", p, err)
	}
	original := err
	owners := disposal.Owners(err)
	if len(owners) != 1 {
		t.Fatal("missing late-startup owner", err)
	}
	lease.TrackCleanup(err)
	var allowed atomic.Bool
	failure := errors.New("late runtime unmap failure")
	releaseOwner := disposal.New(func(context.Context) error {
		if !allowed.Load() {
			return failure
		}
		return nil
	})
	debt := disposal.Retain(nil, failure, releaseOwner)
	completed <- debt
	if e := disposal.Retry(ctx, original); !errors.Is(e, failure) {
		t.Fatal("late cleanup failure was ignored", e)
	}
	if owners[0].Complete() || releaseOwner.Complete() {
		t.Fatal("unreleased resource reported disposed")
	}
	if _, occupied := pool.Usage(); occupied != 1 {
		t.Fatal("unreleased startup returned Fork slot")
	}
	allowed.Store(true)
	if e := disposal.Retry(ctx, original); e != nil {
		t.Fatal(e)
	}
	if !owners[0].Complete() || !releaseOwner.Complete() {
		t.Fatal("recovery did not complete both owners")
	}
	for {
		_, occupied := pool.Usage()
		if occupied == 0 {
			break
		}
		select {
		case <-ctx.Done():
			t.Fatal("recovered lease retained", ctx.Err())
		default:
			time.Sleep(time.Millisecond)
		}
	}
	if !strings.Contains(original.Error(), "invalid guest frame") {
		t.Fatal("original startup failure rewritten", original)
	}
}
