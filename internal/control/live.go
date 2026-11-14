package control

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/disposal"
	endpoint "github.com/masahitojp/mariamem/internal/live"
)

type liveChild struct {
	db        *db
	mu        sync.Mutex
	attempted bool
}

func (c *liveChild) Address() string {
	return net.JoinHostPort("127.0.0.1", strconv.Itoa(c.db.server.Port()))
}
func (c *liveChild) Capacity() int  { return c.db.server.Capacity() }
func (c *liveChild) Failure() error { return c.db.server.Failure() }
func (c *liveChild) WaitDisconnected(ctx context.Context) error {
	c.mu.Lock()
	closed := c.db.closed
	c.mu.Unlock()
	if closed {
		return nil
	}
	for c.db.server.Active() != 0 {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(5 * time.Millisecond):
		}
	}
	return nil
}
func (c *liveChild) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	var err error
	if !c.attempted {
		c.attempted = true
		err = c.db.close()
	} else {
		ctx, cancel := context.WithTimeout(context.Background(), c.db.shutdown)
		err = c.db.retryCleanup(ctx)
		cancel()
	}
	// Keep the log open while an unjoined guest can still write to it.
	cleanup := disposal.CleanupAfter(err, func() error {
		return cleanupOwnedLog(c.db.log, c.db.logPath, true)
	})
	err = errors.Join(err, cleanup)
	c.db.settle(err)
	return err
}
func (m *manager) createLive(ctx context.Context, r Request) (map[string]any, error) {
	m.mu.Lock()
	base := m.snaps[r.Handle]
	m.mu.Unlock()
	if base == nil {
		return map[string]any{"closed": false}, diagnostic.Wrap("closed", "live_precondition", errors.New("snapshot is closed"))
	}
	if base.forkLimit().MaxForks() < 2 {
		return invalid("live_precondition", errors.New("Live requires max_forks >= 2"))
	}
	factory := endpoint.Factory{
		Check: func() error {
			base.mu.RLock()
			defer base.mu.RUnlock()
			if base.closed {
				return errors.New("snapshot is closed")
			}
			return nil
		},
		Reserve: func(ctx context.Context, recover bool) (*endpoint.Reservation, error) {
			if err := ctx.Err(); err != nil {
				return nil, err
			}
			lease, err := base.forkLimit().TryAcquire(recover)
			if err != nil {
				return nil, diagnostic.Wrap(capacityCode(err), "live_capacity", base.forkLimit().Describe(err))
			}
			return &endpoint.Reservation{Cancel: lease.Cancel, Start: func(ctx context.Context) (endpoint.Child, error) {
				base.mu.RLock()
				defer base.mu.RUnlock()
				if base.closed {
					lease.Cancel()
					return nil, errors.New("snapshot is closed")
				}
				if err := lease.Activate(); err != nil {
					lease.Cancel()
					return nil, admission(err)
				}
				token := make([]byte, 16)
				if _, err := rand.Read(token); err != nil {
					lease.Settle(nil)
					return nil, err
				}
				childRequest := Request{LogPath: filepath.Join(filepath.Dir(r.LogPath), "live-"+hex.EncodeToString(token)+".log")}
				child, err := makeDB(ctx, childRequest, base, true)
				if err != nil {
					settleStartup(lease, err)
					return endpoint.RetainStartup(err, lease, base.shutdown), err
				}
				child.lease = lease
				return &liveChild{db: child}, nil
			}}, nil
		},
	}
	live, err := endpoint.New(ctx, factory, base.shutdown)
	if err != nil {
		if live != nil {
			m.mu.Lock()
			id := m.next()
			m.lives[id] = live
			m.mu.Unlock()
		}
		return map[string]any{"closed": false}, err
	}
	m.mu.Lock()
	id := m.next()
	m.lives[id] = live
	m.mu.Unlock()
	return map[string]any{"live": map[string]any{"handle": id, "host": "127.0.0.1", "port": live.Port(), "user": "root", "password": "", "database": "test"}, "status": live.Status(), "closed": false}, nil
}

func removeLog(path string) error {
	if path == "" {
		return nil
	}
	err := os.Remove(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	return err
}
func (m *manager) callLive(ctx context.Context, r Request) (map[string]any, error) {
	m.mu.Lock()
	live := m.lives[r.Handle]
	m.mu.Unlock()
	if live == nil {
		if r.Op == "live_close" {
			return map[string]any{"closed": true}, nil
		}
		return map[string]any{"closed": true}, diagnostic.Wrap("closed", "live_control", errors.New("live is closed"))
	}
	var err error
	switch r.Op {
	case "live_reset":
		timeout, e := duration(r.Timeout, 120*time.Second)
		if e != nil {
			return map[string]any{"closed": false}, diagnostic.Wrap("invalid_options", "live_precondition", e)
		}
		drain, e := duration(r.DrainTimeout, 5*time.Second)
		if e != nil {
			return map[string]any{"closed": false}, diagnostic.Wrap("invalid_options", "live_precondition", e)
		}
		operation, cancel := context.WithTimeout(ctx, timeout)
		defer cancel()
		err = live.Reset(operation, drain)
	case "live_close":
		err = live.Close()
		if err == nil {
			m.mu.Lock()
			delete(m.lives, r.Handle)
			m.mu.Unlock()
		}
	}
	status := live.Status()
	return map[string]any{"status": status, "closed": status.State == "closed", "live_committed": r.Op == "live_reset" && err == nil}, err
}
