// Package control owns Python's automatically managed host. SQL reaches each
// independent Server directly; only lifecycle requests use this protocol.
package control

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"sync"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/host"
	"github.com/masahitojp/mariamem/internal/runtimekind"
	"github.com/masahitojp/mariamem/internal/snapshot"
)

type Request struct {
	TransferPath    string `json:"transfer_path"`
	ID              uint64 `json:"id"`
	Op              string `json:"op"`
	Handle          uint64 `json:"handle"`
	Target          uint64 `json:"target"`
	Rollback        bool   `json:"rollback"`
	Timeout         string `json:"timeout"`
	QueryTimeout    string `json:"query_timeout"`
	StartupTimeout  string `json:"startup_timeout"`
	ShutdownTimeout string `json:"shutdown_timeout"`
	LogPath         string `json:"log_path"`
}
type db struct {
	gate                     chan struct{}
	server                   *host.Server
	query, startup, shutdown time.Duration
	id                       string
	log                      *os.File
	logPath                  string
	closed                   bool
}
type baseline struct {
	mu                       sync.RWMutex
	owned                    *snapshot.Owned
	query, startup, shutdown time.Duration
	closed                   bool
}
type manager struct {
	mu      sync.Mutex
	seq     uint64
	dbs     map[uint64]*db
	snaps   map[uint64]*baseline
	pending map[uint64]context.CancelFunc
	wg      sync.WaitGroup
}

func newManager() *manager {
	return &manager{dbs: map[uint64]*db{}, snaps: map[uint64]*baseline{}, pending: map[uint64]context.CancelFunc{}}
}
func duration(s string, fallback time.Duration) (time.Duration, error) {
	if s == "" {
		return fallback, nil
	}
	d, e := time.ParseDuration(s)
	if e != nil || d <= 0 {
		return 0, errors.New("timeouts must be positive and finite")
	}
	return d, nil
}
func lockDB(ctx context.Context, d *db) error {
	select {
	case d.gate <- struct{}{}:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}
func (d *db) close() error {
	if d.closed {
		return nil
	}
	d.closed = true
	ctx, cancel := context.WithTimeout(context.Background(), d.shutdown)
	defer cancel()
	return errors.Join(d.server.Close(ctx), d.log.Close())
}
func (d *db) logs() string {
	f, e := os.Open(d.logPath)
	if e != nil {
		return ""
	}
	defer f.Close()
	st, e := f.Stat()
	if e != nil {
		return ""
	}
	b, e := io.ReadAll(io.NewSectionReader(f, max(0, st.Size()-16384), 16384))
	if e != nil {
		return ""
	}
	return string(b)
}
func (m *manager) next() uint64 { m.seq++; return m.seq }
func (m *manager) create(ctx context.Context, r Request, base *baseline) (map[string]any, error) {
	q, st, sh := 30*time.Second, 120*time.Second, 30*time.Second
	if base != nil {
		q, st, sh = base.query, base.startup, base.shutdown
	}
	var e error
	if q, e = duration(r.QueryTimeout, q); e != nil {
		return nil, e
	}
	if st, e = duration(r.StartupTimeout, st); e != nil {
		return nil, e
	}
	if sh, e = duration(r.ShutdownTimeout, sh); e != nil {
		return nil, e
	}
	f, e := os.OpenFile(r.LogPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if e != nil {
		return nil, e
	}
	startup, cancel := context.WithTimeout(ctx, st)
	defer cancel()
	var backing *snapshot.Owned
	if base != nil {
		backing = base.owned
	}
	s, e := host.StartGenerated(startup, backing, q, f)
	if e != nil {
		f.Close()
		return nil, e
	}
	d := &db{gate: make(chan struct{}, 1), server: s, query: q, startup: st, shutdown: sh, log: f, logPath: r.LogPath}
	token := make([]byte, 16)
	if _, e = rand.Read(token); e != nil {
		d.close()
		return nil, e
	}
	d.id = hex.EncodeToString(token)
	if e = ctx.Err(); e != nil {
		d.close()
		return nil, e
	}
	m.mu.Lock()
	id := m.next()
	m.dbs[id] = d
	m.mu.Unlock()
	return map[string]any{"database": map[string]any{"handle": id, "id": d.id, "host": "127.0.0.1", "port": s.Port(), "user": "root", "password": "", "database": "test", "pid": os.Getpid(), "runtime_pid": os.Getpid(), "capabilities": []string{"status", "close", "text-query", "reconnect", "snapshot", "fork"}, "max_connections": s.Capacity()}}, nil
}
func (m *manager) call(ctx context.Context, r Request) (result map[string]any, err error) {
	switch r.Op {
	case "start":
		if r.TransferPath != "" {
			b, e := snapshot.Import(r.TransferPath, runtimekind.GuestSHA256)
			if e != nil {
				return nil, e
			}
			defer b.Close()
			return m.create(ctx, r, &baseline{owned: b, query: 30 * time.Second, startup: 120 * time.Second, shutdown: 30 * time.Second})
		}
		return m.create(ctx, r, nil)
	case "handoff":
		m.mu.Lock()
		b := m.snaps[r.Handle]
		m.mu.Unlock()
		if b == nil {
			return nil, errors.New("snapshot is closed")
		}
		b.mu.RLock()
		defer b.mu.RUnlock()
		if b.closed {
			return nil, errors.New("snapshot is closed")
		}
		return map[string]any{}, b.owned.Handoff(r.TransferPath, runtimekind.GuestSHA256)
	case "fork":
		m.mu.Lock()
		b := m.snaps[r.Handle]
		m.mu.Unlock()
		if b == nil {
			return nil, errors.New("snapshot is closed")
		}
		b.mu.RLock()
		defer b.mu.RUnlock()
		if b.closed {
			return nil, errors.New("snapshot is closed")
		}
		return m.create(ctx, r, b)
	case "snapshot_close":
		m.mu.Lock()
		b := m.snaps[r.Handle]
		delete(m.snaps, r.Handle)
		m.mu.Unlock()
		if b == nil {
			return map[string]any{}, nil
		}
		b.mu.Lock()
		defer b.mu.Unlock()
		b.closed = true
		return map[string]any{}, b.owned.Close()
	}
	m.mu.Lock()
	d := m.dbs[r.Handle]
	m.mu.Unlock()
	if d == nil {
		if r.Op == "db_close" {
			return map[string]any{"closed": true}, nil
		}
		return nil, errors.New("database is closed")
	}
	if e := lockDB(ctx, d); e != nil {
		return nil, e
	}
	defer func() { <-d.gate }()
	if d.closed && r.Op != "db_close" {
		return map[string]any{"closed": true}, errors.New("database is closed")
	}
	switch r.Op {
	case "status":
		if e := d.server.Failure(); e != nil {
			return map[string]any{"closed": true}, diagnostic.Wrap("unusable", "host_control", fmt.Errorf("database instance terminated: %w", e))
		}
		return map[string]any{"state": "ready", "active_connections": d.server.Active(), "busy": d.server.Busy(), "logs": d.logs()}, nil
	case "logs":
		return map[string]any{"logs": d.logs()}, nil
	case "snapshot":
		timeout, e := duration(r.Timeout, 120*time.Second)
		if e != nil {
			return nil, e
		}
		capture, cancel := context.WithTimeout(ctx, timeout)
		defer cancel()
		owned, consumed, e := d.server.SnapshotHeap(capture, r.Rollback)
		result = map[string]any{"closed": consumed, "logs": d.logs()}
		if consumed {
			d.closed = true
			m.mu.Lock()
			delete(m.dbs, r.Handle)
			m.mu.Unlock()
			e = errors.Join(e, d.log.Close())
		}
		if e == nil {
			e = ctx.Err()
		}
		if e != nil {
			if owned != nil {
				e = errors.Join(e, owned.Close())
			}
			return result, e
		}
		b := &baseline{owned: owned, query: d.query, startup: d.startup, shutdown: d.shutdown}
		m.mu.Lock()
		id := m.next()
		m.snaps[id] = b
		m.mu.Unlock()
		result["snapshot"] = id
		return result, nil
	case "db_close":
		e := d.close()
		m.mu.Lock()
		delete(m.dbs, r.Handle)
		m.mu.Unlock()
		return map[string]any{"closed": true, "logs": d.logs()}, e
	default:
		return nil, errors.New("operation is not implemented")
	}
}
func (m *manager) cleanup() {
	m.mu.Lock()
	dbs := m.dbs
	snaps := m.snaps
	m.dbs = map[uint64]*db{}
	m.snaps = map[uint64]*baseline{}
	m.mu.Unlock()
	var wg sync.WaitGroup
	for _, d := range dbs {
		wg.Add(1)
		go func() { defer wg.Done(); d.gate <- struct{}{}; defer func() { <-d.gate }(); _ = d.close() }()
	}
	for _, b := range snaps {
		wg.Add(1)
		go func() { defer wg.Done(); b.mu.Lock(); defer b.mu.Unlock(); _ = b.owned.Close() }()
	}
	wg.Wait()
}
func replyError(r map[string]any, e error) {
	if e == nil {
		r["ok"] = true
		return
	}
	r["ok"] = false
	code := "unusable"
	stage := "host_control"
	var detail *diagnostic.Error
	if errors.As(e, &detail) {
		code, stage = detail.Code, detail.Stage
	}
	var reject *host.Rejected
	if errors.As(e, &reject) {
		code = reject.Code
	}
	code = diagnostic.ControlCode(e, code)

	r["error"] = map[string]string{"code": code, "stage": stage, "message": e.Error()}
}

// Run handles owner EOF/signal cooperatively with a bounded final host wait.
// No individual request cancellation terminates this shared process.
func Run(parent context.Context, in io.Reader, out io.Writer) error {
	return runWith(parent, in, out, newManager(), nil)
}

func runWith(parent context.Context, in io.Reader, out io.Writer, m *manager, operation func(context.Context, Request) (map[string]any, error)) error {
	owner, cancelOwner := context.WithCancel(parent)
	defer cancelOwner()
	if operation == nil {
		operation = m.call
	}
	var encMu sync.Mutex
	enc := json.NewEncoder(out)
	send := func(v any) error { encMu.Lock(); defer encMu.Unlock(); return enc.Encode(v) }
	if e := send(map[string]any{"event": "ready", "protocol": 2, "pid": os.Getpid(), "guest_sha256": runtimekind.GuestSHA256}); e != nil {
		return e
	}
	messages := make(chan Request)
	fail := make(chan error, 1)
	go func() {
		scanner := bufio.NewScanner(in)
		scanner.Buffer(make([]byte, 4096), 1<<20)
		for scanner.Scan() {
			var r Request
			if e := json.Unmarshal(scanner.Bytes(), &r); e != nil {
				fail <- e
				return
			}
			select {
			case messages <- r:
			case <-owner.Done():
				return
			}
		}
		fail <- scanner.Err()
	}()
	var terminal error
loop:
	for {
		select {
		case <-owner.Done():
			terminal = owner.Err()
			break loop
		case terminal = <-fail:
			break loop
		case r := <-messages:
			if r.Op == "cancel" {
				m.mu.Lock()
				stop := m.pending[r.Target]
				m.mu.Unlock()
				if stop != nil {
					stop()
				}
				continue
			}
			if r.ID == 0 {
				terminal = errors.New("missing request id")
				break loop
			}
			if r.Op == "shutdown" {
				m.mu.Lock()
				idle := len(m.dbs) == 0 && len(m.snaps) == 0 && len(m.pending) == 0
				m.mu.Unlock()
				if idle {
					_ = send(map[string]any{"id": r.ID, "ok": true})
					break loop
				}
				_ = send(map[string]any{"id": r.ID, "ok": false, "error": map[string]string{"code": "busy", "message": "host still owns resources"}})
				continue
			}
			ctx, stop := context.WithCancel(owner)
			m.mu.Lock()
			_, duplicate := m.pending[r.ID]
			if !duplicate {
				m.pending[r.ID] = stop
			}
			m.mu.Unlock()
			if duplicate {
				stop()
				terminal = errors.New("duplicate request id")
				break loop
			}
			m.wg.Add(1)
			go func() {
				defer m.wg.Done()
				defer stop()
				result, e := operation(ctx, r)
				if ctx.Err() != nil && result != nil {
					if value, ok := result["database"].(map[string]any); ok {
						if handle, ok := value["handle"].(uint64); ok {
							_, cleanup := m.call(context.Background(), Request{Op: "db_close", Handle: handle})
							e = errors.Join(e, cleanup)
						}
						delete(result, "database")
					}
					if handle, ok := result["snapshot"].(uint64); ok {
						_, cleanup := m.call(context.Background(), Request{Op: "snapshot_close", Handle: handle})
						e = errors.Join(e, cleanup)
						delete(result, "snapshot")
					}
					e = errors.Join(e, ctx.Err())
				}
				if result == nil {
					result = map[string]any{}
				}
				result["id"] = r.ID
				replyError(result, e)
				m.mu.Lock()
				delete(m.pending, r.ID)
				m.mu.Unlock()
				if e := send(result); e != nil {
					cancelOwner()
				}
			}()
		}
	}
	cancelOwner()
	done := make(chan struct{})
	go func() { m.wg.Wait(); m.cleanup(); close(done) }()
	select {
	case <-done:
	case <-time.After(45 * time.Second):
		return errors.New("shared host cooperative cleanup timed out")
	}
	return terminal
}
