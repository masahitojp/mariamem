package live

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/forklimit"
)

type limitedEcho struct {
	*echoChild
	lease *forklimit.Lease
}

func (c *limitedEcho) Close() error {
	err := c.echoChild.Close()
	c.lease.Settle(err)
	return err
}

func limitedFactory(t *testing.T, p *forklimit.Pool, children ...*echoChild) Factory {
	t.Helper()
	index := 0
	return Factory{Check: func() error { return nil }, Reserve: func(ctx context.Context, recover bool) (*Reservation, error) {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		l, err := p.TryAcquire(recover)
		if err != nil {
			return nil, err
		}
		return &Reservation{Cancel: l.Cancel, Start: func(context.Context) (Child, error) {
			if err := l.Activate(); err != nil {
				return nil, err
			}
			if index >= len(children) {
				t.Fatal("unexpected startup")
				return nil, errors.New("unexpected startup")
			}
			c := &limitedEcho{echoChild: children[index], lease: l}
			index++
			return c, nil
		}}, nil
	}}
}

func TestRealLimiterCapacityBusyPreservesEndpointAndReleasesDrainReservation(t *testing.T) {
	p, _ := forklimit.New(2)
	a, b := echo(t), echo(t)
	e := newEndpoint(t, limitedFactory(t, p, a, b))
	extra, _ := p.TryAcquire(false)
	if err := extra.Activate(); err != nil {
		t.Fatal(err)
	}
	if err := e.Reset(context.Background(), time.Second); !errors.Is(err, forklimit.ErrFull) {
		t.Fatal(err)
	}
	if e.Status().State != "ready" || e.Status().Generation != 0 || a.closed {
		t.Fatal(e.Status())
	}
	c := connected(t, e)
	exchange(t, c, []byte("busy preserves old child"))
	extra.Settle(nil)
	if err := e.Reset(context.Background(), time.Millisecond); err == nil {
		t.Fatal("drain admitted live connection")
	}
	// Failed drain returns its unused replacement reservation.
	probe, err := p.TryAcquire(false)
	if err != nil {
		t.Fatal("drain leaked slot", err)
	}
	probe.Cancel()
	c.Close()
	waitActive(t, e, 0)
	if err := e.Reset(context.Background(), time.Second); err != nil {
		t.Fatal(err)
	}
	if e.Status().Generation != 1 || !a.closed {
		t.Fatal(e.Status())
	}
}

func TestRealLimiterCapTwoCleanupRetryBeforeRecovery(t *testing.T) {
	p, _ := forklimit.New(2)
	a, b, c := echo(t), echo(t), echo(t)
	e := newEndpoint(t, limitedFactory(t, p, a, b, c))
	oldCause, newCause := errors.New("old cleanup"), errors.New("candidate cleanup")
	a.closeErr, b.closeErr = oldCause, newCause
	if err := e.Reset(context.Background(), time.Second); !errors.Is(err, oldCause) || !errors.Is(err, newCause) {
		t.Fatal(err)
	}
	if e.Status().State != "failed" || e.Status().Generation != 0 {
		t.Fatal(e.Status())
	}
	if _, err := p.TryAcquire(true); !errors.Is(err, forklimit.ErrCleanup) {
		t.Fatal("unresolved debt forgiven", err)
	}
	b.closeErr = newCause
	if err := e.Reset(context.Background(), time.Second); !errors.Is(err, newCause) {
		t.Fatal("retry failure lost", err)
	}
	if e.Status().State != "failed" {
		t.Fatal(e.Status())
	}
	if err := e.Reset(context.Background(), time.Second); err != nil {
		t.Fatal(err)
	}
	if e.Status().State != "ready" || e.Status().Generation != 1 || !a.closed || !b.closed {
		t.Fatal(e.Status())
	}
	// One current child remains; the second slot is free, but there is no third.
	extra, err := p.TryAcquire(false)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := p.TryAcquire(false); !errors.Is(err, forklimit.ErrFull) {
		t.Fatal(err)
	}
	extra.Cancel()
}

func TestRealLimiterExplicitResetCannotForgiveAnotherOwner(t *testing.T) {
	p, _ := forklimit.New(2)
	a, b := echo(t), echo(t)
	e := newEndpoint(t, limitedFactory(t, p, a, b))
	other, _ := p.TryAcquire(false)
	_ = other.Activate()
	cause := errors.New("another owner still cleaning")
	other.Settle(cause)
	if err := e.Reset(context.Background(), time.Second); !errors.Is(err, cause) {
		t.Fatal(err)
	}
	if a.closed || e.Status().State != "ready" {
		t.Fatal("healthy child changed before reservation")
	}
	other.Settle(nil)
	if _, err := p.TryAcquire(false); !errors.Is(err, forklimit.ErrCleanup) {
		t.Fatal("automatically reopened")
	}
	if err := e.Reset(context.Background(), time.Second); err != nil {
		t.Fatal(err)
	}
	p.Close()
	if err := e.Reset(context.Background(), time.Second); !errors.Is(err, forklimit.ErrClosed) {
		t.Fatal(err)
	}
	if e.Status().State != "ready" || e.Status().Generation != 1 {
		t.Fatal(e.Status())
	}
}
