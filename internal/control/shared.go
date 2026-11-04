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
	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
	"github.com/masahitojp/mariamem/internal/host"
	endpoint "github.com/masahitojp/mariamem/internal/live"
	"github.com/masahitojp/mariamem/internal/runtimekind"
	"github.com/masahitojp/mariamem/internal/snapshot"
)

type Request struct {
	MaxForks        json.RawMessage `json:"max_forks,omitempty"`
	ForkTimeout     json.RawMessage `json:"fork_timeout,omitempty"`
	Reservation     json.RawMessage `json:"reservation,omitempty"`
	Cleanup         json.RawMessage `json:"cleanup,omitempty"`
	OwnedLog        json.RawMessage `json:"owned_log,omitempty"`
	TransferPath    string          `json:"transfer_path"`
	ID              uint64          `json:"id"`
	Op              string          `json:"op"`
	Handle          uint64          `json:"handle"`
	Target          uint64          `json:"target"`
	Rollback        bool            `json:"rollback"`
	Timeout         string          `json:"timeout"`
	DrainTimeout    string          `json:"drain_timeout"`
	QueryTimeout    string          `json:"query_timeout"`
	StartupTimeout  string          `json:"startup_timeout"`
	ShutdownTimeout string          `json:"shutdown_timeout"`
	LogPath         string          `json:"log_path"`
}
type db struct {
	gate                     chan struct{}
	server                   *host.Server
	query, startup, shutdown time.Duration
	id                       string
	log                      *os.File
	logPath                  string
	closed                   bool
	closeErr                 error
	lease                    *forklimit.Lease
	captureDebt              error
	ownedLog                 bool
	logTail                  string
}
type baseline struct {
	mu                       sync.RWMutex
	owned                    *snapshot.Owned
	query, startup, shutdown time.Duration
	closed                   bool
	limit                    *forklimit.Pool
	limitOnce                sync.Once
}
type manager struct {
	mu           sync.Mutex
	seq          uint64
	lives        map[uint64]*endpoint.Endpoint
	dbs          map[uint64]*db
	snaps        map[uint64]*baseline
	pending      map[uint64]context.CancelFunc
	wg           sync.WaitGroup
	reservations map[string]*reservation
	retained     map[string]error
}

func newManager() *manager {
	return &manager{lives: map[uint64]*endpoint.Endpoint{}, dbs: map[uint64]*db{}, snaps: map[uint64]*baseline{}, pending: map[uint64]context.CancelFunc{}, reservations: map[string]*reservation{}, retained: map[string]error{}}
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
		return d.closeErr
	}
	d.closed = true
	d.logTail = d.logs()
	ctx, cancel := context.WithTimeout(context.Background(), d.shutdown)
	defer cancel()
	err := d.server.Close(ctx)
	d.closeErr = errors.Join(err, disposal.CleanupAfter(err, d.cleanupLog))
	d.settle(d.closeErr)
	return d.closeErr
}

func closeLog(f *os.File) error {
	if f == nil {
		return nil
	}
	err := f.Close()
	if errors.Is(err, os.ErrClosed) {
		return nil
	}
	return err
}
func (d *db) logs() string {
	f, e := os.Open(d.logPath)
	if e != nil {
		return d.logTail
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
func makeDB(ctx context.Context, r Request, base *baseline, ownedLog bool) (*db, error) {
	if len(r.OwnedLog) != 0 {
		var flag bool
		if json.Unmarshal(r.OwnedLog, &flag) != nil {
			return nil, diagnostic.Wrap("invalid_options", "fork_options", errors.New("owned_log must be a bool"))
		}
		ownedLog = ownedLog || flag
	}
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
	// Only remove a private Live log after this call successfully created it.
	// Public/requested logs remain with their caller for diagnostics.
	cleanupLog := func() error {
		var removal error
		if ownedLog {
			removal = removeLog(r.LogPath)
		}
		return errors.Join(closeLog(f), removal)
	}
	startup, cancel := context.WithTimeout(ctx, st)
	defer cancel()
	var backing *snapshot.Owned
	if base != nil {
		backing = base.owned
	}
	s, e := host.StartGenerated(startup, backing, q, f)
	if e != nil {
		return nil, disposal.After(e, cleanupLog)
	}
	d := &db{gate: make(chan struct{}, 1), server: s, query: q, startup: st, shutdown: sh, log: f, logPath: r.LogPath, ownedLog: ownedLog}
	token := make([]byte, 16)
	if _, e = rand.Read(token); e != nil {
		return nil, disposal.After(errors.Join(e, d.close()), cleanupLog)
	}
	d.id = hex.EncodeToString(token)
	if e = ctx.Err(); e != nil {
		return nil, disposal.After(errors.Join(e, d.close()), cleanupLog)
	}
	return d, nil
}
func (m *manager) create(ctx context.Context, r Request, base *baseline, lease *forklimit.Lease) (map[string]any, error) {
	d, err := makeDB(ctx, r, base, false)
	if err != nil {
		settleStartup(lease, err)
		return m.retainFailure(err), err
	}
	d.lease = lease
	s := d.server

	m.mu.Lock()
	id := m.next()
	m.dbs[id] = d
	m.mu.Unlock()
	return map[string]any{"database": map[string]any{"handle": id, "id": d.id, "host": "127.0.0.1", "port": s.Port(), "user": "root", "password": "", "database": "test", "pid": os.Getpid(), "runtime_pid": os.Getpid(), "capabilities": []string{"status", "close", "text-query", "reconnect", "snapshot", "fork"}, "max_connections": s.Capacity()}}, nil
}
func (m *manager) call(ctx context.Context, r Request) (result map[string]any, err error) {
	if r.Op == "snapshot" {
		if _, e := forklimit.DecodeCapacity(r.MaxForks); e != nil {
			return invalid("snapshot_options", e)
		}
	}
	switch r.Op {
	case "fork_reserve", "fork_cancel", "handoff_release", "handoff_abandon", "cleanup_status":
		return m.reservationCall(ctx, r)
	case "live_create":
		return m.createLive(ctx, r)
	case "live_reset", "live_close", "live_status":
		return m.callLive(ctx, r)
	case "start":
		if r.TransferPath != "" {
			b, e := snapshot.Import(r.TransferPath, runtimekind.GuestSHA256)
			if e != nil {
				return nil, e
			}
			defer func() { err = disposal.After(err, b.Close) }()
			return m.create(ctx, r, &baseline{owned: b, query: 30 * time.Second, startup: 120 * time.Second, shutdown: 30 * time.Second}, nil)
		}
		return m.create(ctx, r, nil, nil)
	case "handoff":
		return m.exportReserved(ctx, r)
	case "fork":
		return m.fork(ctx, r)
	case "snapshot_close":
		m.mu.Lock()
		b := m.snaps[r.Handle]
		delete(m.snaps, r.Handle)
		m.mu.Unlock()
		if b == nil {
			return map[string]any{}, nil
		}
		b.forkLimit().Close()
		m.cancelReservations(b)
		b.mu.Lock()
		defer b.mu.Unlock()
		b.closed = true
		return map[string]any{}, b.owned.Close()
	}
	m.mu.Lock()
	d := m.dbs[r.Handle]
	m.mu.Unlock()
	if d == nil {
		if r.Op == "db_close" || r.Op == "db_cleanup" {
			return map[string]any{"closed": true, "disposed": true}, nil
		}
		return nil, errors.New("database is closed")
	}
	if e := lockDB(ctx, d); e != nil {
		return nil, e
	}
	defer func() { <-d.gate }()
	if d.closed && r.Op != "db_close" && r.Op != "db_cleanup" {
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
		capacity, e := forklimit.DecodeCapacity(r.MaxForks)
		if e != nil {
			return invalid("snapshot_options", e)
		}
		capacity, e = forklimit.Resolve(capacity)
		if e != nil {
			return invalid("snapshot_options", e)
		}
		limit, e := forklimit.New(capacity)
		if e != nil {
			return invalid("snapshot_options", e)
		}
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
			d.logTail = d.logs()
			// Retain the handle when cleanup is not confirmed so the private
			// cleanup retry can settle a remote child's source lease later.
			d.closeErr = disposal.CleanupAfter(e, d.cleanupLog)
			e = errors.Join(e, d.closeErr)
		}
		if e == nil {
			e = ctx.Err()
		}
		if e != nil {
			if owned != nil {
				cleanup := owned.Close()
				e = errors.Join(e, cleanup)
				if cleanup != nil {
					d.captureDebt = errors.Join(d.captureDebt, cleanup)
				}
			}
			if consumed {
				m.finishConsumed(d, r.Handle, result, e)
			}
			return result, e
		}
		if consumed {
			m.finishConsumed(d, r.Handle, result, nil)
		}
		b := &baseline{owned: owned, query: d.query, startup: d.startup, shutdown: d.shutdown, limit: limit}
		m.mu.Lock()
		id := m.next()
		m.snaps[id] = b
		m.mu.Unlock()
		result["snapshot"] = id
		result["max_forks"] = capacity
		return result, nil
	case "db_close":
		e := d.close()
		m.mu.Lock()
		if d.disposed() {
			delete(m.dbs, r.Handle)
		}
		m.mu.Unlock()
		result = map[string]any{"closed": true, "disposed": d.disposed(), "logs": d.logs()}
		if !d.disposed() {
			result["cleanup_handle"] = r.Handle
		}
		return result, e
	case "db_cleanup":
		e := d.retryCleanup(ctx)
		if d.disposed() {
			m.mu.Lock()
			delete(m.dbs, r.Handle)
			m.mu.Unlock()
		}
		return map[string]any{"closed": true, "disposed": d.disposed()}, e
	default:
		return nil, errors.New("operation is not implemented")
	}
}
func (m *manager) cleanup() error {
	m.mu.Lock()
	lives := m.lives
	m.lives = map[uint64]*endpoint.Endpoint{}
	dbs := m.dbs
	snaps := m.snaps
	reservations, retained := m.reservations, m.retained
	m.reservations = map[string]*reservation{}
	m.retained = map[string]error{}
	m.dbs = map[uint64]*db{}
	m.snaps = map[uint64]*baseline{}
	m.mu.Unlock()
	var wg sync.WaitGroup
	var cleanupMu sync.Mutex
	var cleanupErr error
	collect := func(err error) { cleanupMu.Lock(); cleanupErr = errors.Join(cleanupErr, err); cleanupMu.Unlock() }
	for _, b := range snaps {
		b.forkLimit().Close()
	}
	for _, live := range lives {
		wg.Add(1)
		go func() { defer wg.Done(); collect(live.FinalCleanup()) }()
	}
	wg.Wait()
	for _, d := range dbs {
		wg.Add(1)
		go func() {
			defer wg.Done()
			d.gate <- struct{}{}
			defer func() { <-d.gate }()
			ctx, cancel := context.WithTimeout(context.Background(), d.shutdown)
			defer cancel()
			collect(errors.Join(d.close(), d.retryCleanup(ctx)))
		}()
	}
	for _, b := range snaps {
		b.forkLimit().Close()
		wg.Add(1)
		go func() { defer wg.Done(); b.mu.Lock(); defer b.mu.Unlock(); collect(b.owned.Close()) }()
	}
	wg.Wait()
	for _, a := range reservations {
		a.lease.Cancel()
		if a.path != "" {
			collect(disposal.RemoveAfter(nil, a.path))
		}
	}
	for _, cause := range retained {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		collect(disposal.Retry(ctx, cause))
		cancel()
	}
	return cleanupErr
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
	if e := send(map[string]any{"event": "ready", "protocol": 2, "capabilities": []string{"live-v1", "fork-limit-v1"}, "pid": os.Getpid(), "guest_sha256": runtimekind.GuestSHA256}); e != nil {
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
				idle := len(m.dbs) == 0 && len(m.snaps) == 0 && len(m.lives) == 0 && len(m.pending) == 0 && len(m.reservations) == 0 && len(m.retained) == 0
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
				committed := r.Op == "live_reset" && e == nil && result != nil && result["live_committed"] == true
				if (ctx.Err() != nil || e != nil) && result != nil && !committed {
					if id, ok := result["reservation"].(string); ok {
						raw, _ := json.Marshal(id)
						_, cleanup := m.reservationCall(context.Background(), Request{Op: "fork_cancel", Handle: r.Handle, Reservation: raw})
						e = errors.Join(e, cleanup)
						delete(result, "reservation")
					}
					if id, ok := result["lease"].(string); ok {
						raw, _ := json.Marshal(id)
						_, cleanup := m.reservationCall(context.Background(), Request{Op: "handoff_release", Handle: r.Handle, Reservation: raw})
						e = errors.Join(e, cleanup)
					}
					if value, ok := result["database"].(map[string]any); ok {
						if handle, ok := value["handle"].(uint64); ok {
							state, cleanup := m.call(context.Background(), Request{Op: "db_close", Handle: handle})
							e = errors.Join(e, cleanup)
							result["closed"] = true
							result["disposed"] = state["disposed"]
							if state["disposed"] != true {
								result["cleanup_handle"] = handle
							}
						}
						delete(result, "database")
					}
					if value, ok := result["live"].(map[string]any); ok {
						if handle, ok := value["handle"].(uint64); ok {
							_, cleanup := m.call(context.Background(), Request{Op: "live_close", Handle: handle})
							e = errors.Join(e, cleanup)
						}
						delete(result, "live")
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
	done := make(chan error, 1)
	go func() { m.wg.Wait(); done <- m.cleanup() }()
	select {
	case cleanupErr := <-done:
		return errors.Join(terminal, cleanupErr)
	case <-time.After(45 * time.Second):
		return errors.New("shared host cooperative cleanup timed out")
	}
}
