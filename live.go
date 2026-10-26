package mariamem

import (
	"context"
	"errors"
	"net"
	"strconv"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	endpoint "github.com/masahitojp/mariamem/internal/live"
)

// Live owns a stable localhost endpoint over replaceable private Forks.
// Stop application work and close all physical SQL connections before Reset.
// Keep its parent Snapshot open until no further resets are needed. Do not copy.
type Live struct {
	endpoint *endpoint.Endpoint
	info     ConnectionInfo
}

// LiveStatus describes the endpoint; Generation changes only on a committed reset.
type LiveStatus = endpoint.Status

// ResetOptions bounds physical-connection draining independently of ctx.
type ResetOptions struct{ DrainTimeout time.Duration }

type liveChild struct{ *Database }

func (c liveChild) Address() string {
	i := c.ConnectionInfo()
	return net.JoinHostPort(i.Host, strconv.Itoa(i.Port))
}
func (c liveChild) Capacity() int  { return c.server.Capacity() }
func (c liveChild) Failure() error { return c.Err() }

// Disposal retries are private to Live; Database.Close keeps its stored result.
func (c liveChild) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if !c.closed {
		return c.closeLocked()
	}
	var err error
	if c.server != nil {
		ctx, cancel := context.WithTimeout(context.Background(), c.opts.ShutdownTimeout)
		err = c.server.Close(ctx)
		cancel()
	}
	return hostError(errors.Join(err, c.removeTemporary()), "close", true)
}
func (c liveChild) WaitDisconnected(ctx context.Context) error {
	c.mu.Lock()
	closed := c.closed
	c.mu.Unlock()
	// A previous Close stopped admission. Close must still confirm disposal.
	if closed {
		return nil
	}
	return c.Database.WaitDisconnected(ctx)
}

// Live starts one child and a stable endpoint, borrowing this Snapshot.
// If creation cleanup fails, the non-nil returned Live is a closed cleanup-only
// owner; retain it and report its Close error. Its ctx governs creation only; use Close to end the endpoint lifetime.
func (s *Snapshot) Live(ctx context.Context) (*Live, error) {
	factory := endpoint.Factory{
		Check: func() error {
			s.mu.RLock()
			defer s.mu.RUnlock()
			if s.closed || s.backing == nil {
				return ErrClosed
			}
			return nil
		},
		Start: func(ctx context.Context) (endpoint.Child, error) {
			db, err := s.Fork(ctx)
			if err != nil {
				return nil, err
			}
			return liveChild{db}, nil
		},
	}
	e, err := endpoint.New(ctx, factory, s.opts.ShutdownTimeout)
	if err != nil {
		if e != nil {
			return &Live{endpoint: e}, liveError(err, true)
		}
		return nil, liveError(err, false)
	}
	return &Live{endpoint: e, info: ConnectionInfo{Host: "127.0.0.1", Port: e.Port(), User: "root", Database: "test"}}, nil
}
func (l *Live) ConnectionInfo() ConnectionInfo { return l.info }
func (l *Live) DSN() string                    { return (&Database{info: l.info}).DSN() }
func (l *Live) Status() LiveStatus             { return l.endpoint.Status() }

// Reset installs a fresh baseline child only after all physical sessions drain.
// Idle pooled connections also block it. A busy error preserves the old data;
// a replacement failure blocks SQL until explicit successful Reset or Close.
// Cancellation after commit returns success. Cleanup can outlast ctx's deadline.
func (l *Live) Reset(ctx context.Context, opts ResetOptions) error {
	if opts.DrainTimeout < 0 {
		return liveError(diagnostic.Wrap("invalid_options", "live_precondition", errors.New("drain timeout must not be negative")), false)
	}
	drain := opts.DrainTimeout
	if drain == 0 {
		drain = 5 * time.Second
	}
	return liveError(l.endpoint.Reset(ctx, drain), l.Status().State == "closed")
}

// Close stops connections and disposes all children; repeated calls retain its result.
func (l *Live) Close() error { return liveError(l.endpoint.Close(), true) }
func liveError(err error, closed bool) error {
	if err == nil {
		return nil
	}
	code, stage := "unusable", "live_control"
	var detail *diagnostic.Error
	if errors.As(err, &detail) {
		code, stage = detail.Code, detail.Stage
	}
	return &HostError{Code: diagnostic.ControlCode(err, code), Stage: stage, Closed: closed, Err: err}
}
