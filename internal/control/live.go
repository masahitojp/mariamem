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
	endpoint "github.com/masahitojp/mariamem/internal/live"
)

type liveChild struct {
	db       *db
	once     sync.Once
	closeErr error
}

func (c *liveChild) Address() string {
	return net.JoinHostPort("127.0.0.1", strconv.Itoa(c.db.server.Port()))
}
func (c *liveChild) Capacity() int  { return c.db.server.Capacity() }
func (c *liveChild) Failure() error { return c.db.server.Failure() }
func (c *liveChild) WaitDisconnected(ctx context.Context) error {
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
	c.once.Do(func() { c.closeErr = errors.Join(c.db.close(), os.Remove(c.db.logPath)) })
	return c.closeErr
}
func (m *manager) createLive(ctx context.Context, r Request) (map[string]any, error) {
	m.mu.Lock()
	base := m.snaps[r.Handle]
	m.mu.Unlock()
	if base == nil {
		return map[string]any{"closed": false}, diagnostic.Wrap("closed", "live_precondition", errors.New("snapshot is closed"))
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
		Start: func(ctx context.Context) (endpoint.Child, error) {
			base.mu.RLock()
			defer base.mu.RUnlock()
			if base.closed {
				return nil, errors.New("snapshot is closed")
			}
			token := make([]byte, 16)
			if _, err := rand.Read(token); err != nil {
				return nil, err
			}
			childRequest := Request{LogPath: filepath.Join(filepath.Dir(r.LogPath), "live-"+hex.EncodeToString(token)+".log")}
			child, err := makeDB(ctx, childRequest, base)
			if err != nil {
				_ = os.Remove(childRequest.LogPath)
				return nil, err
			}
			return &liveChild{db: child}, nil
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
