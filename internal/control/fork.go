package control

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
	"github.com/masahitojp/mariamem/internal/runtimekind"
)

type reservation struct {
	base   *baseline
	handle uint64
	lease  *forklimit.Lease
	stage  string // reserved, starting, exported
	path   string
}

func invalid(stage string, err error) (map[string]any, error) {
	return map[string]any{"closed": false}, diagnostic.Wrap("invalid_options", stage, err)
}
func admission(err error) error {
	code, stage := "unusable", "fork_admission"
	switch {
	case errors.Is(err, forklimit.ErrCleanup):
	case errors.Is(err, forklimit.ErrClosed):
		code, stage = "closed", "fork_wait"
	case errors.Is(err, forklimit.ErrFull):
		code, stage = "busy", "fork_wait"
	case errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded):
		code, stage = "pool_timeout", "fork_wait"
	case errors.Is(err, forklimit.ErrLease):
		code, stage = "invalid_options", "fork_options"
	}
	return diagnostic.Wrap(code, stage, err)
}
func capacityCode(err error) string {
	var d *diagnostic.Error
	errors.As(admission(err), &d)
	return d.Code
}
func token() (string, error) {
	b := make([]byte, 16)
	_, err := rand.Read(b)
	return hex.EncodeToString(b), err
}
func tokenField(raw json.RawMessage) (string, error) {
	var s string
	if json.Unmarshal(raw, &s) != nil || len(s) != 32 {
		return "", errors.New("expected an issued reservation/cleanup token")
	}
	if _, err := hex.DecodeString(s); err != nil {
		return "", errors.New("invalid reservation/cleanup token")
	}
	return s, nil
}
func (b *baseline) forkLimit() *forklimit.Pool {
	b.limitOnce.Do(func() {
		if b.limit == nil {
			n, _ := forklimit.Resolve(0)
			b.limit, _ = forklimit.New(n)
		}
	})
	return b.limit
}
func pendingCleanup(err error) bool {
	for _, o := range disposal.Owners(err) {
		if !o.Complete() {
			return true
		}
	}
	return false
}
func settleStartup(l *forklimit.Lease, err error) {
	if l == nil {
		return
	}
	if pendingCleanup(err) {
		l.TrackCleanup(err)
	} else {
		l.Settle(nil)
	}
}
func (d *db) disposed() bool {
	if !d.closed || d.captureDebt != nil || pendingCleanup(d.closeErr) {
		return false
	}
	return d.server == nil || d.server.DisposalComplete()
}
func (d *db) settle(err error) {
	if d.lease == nil {
		return
	}
	if d.captureDebt != nil {
		d.lease.Settle(err)
	} else if pendingCleanup(err) {
		d.lease.TrackCleanup(err)
	} else if err == nil || d.disposed() {
		d.lease.Settle(nil)
	} else {
		d.lease.Settle(err)
	}
}
func (d *db) retryCleanup(ctx context.Context) error {
	if err := disposal.Retry(ctx, d.closeErr); err != nil {
		return err
	}
	var err error
	if d.server != nil {
		err = d.server.Close(ctx)
	}
	err = errors.Join(err, disposal.CleanupAfter(err, d.cleanupLog), d.captureDebt)
	if !pendingCleanup(err) && d.captureDebt == nil && (err == nil || d.server == nil || d.server.DisposalComplete()) {
		if d.lease != nil {
			d.lease.Settle(nil)
		}
	}
	return err
}
func (d *db) cleanupLog() error {
	return cleanupOwnedLog(d.log, d.logPath, d.ownedLog)
}

func (m *manager) retainFailure(err error) map[string]any {
	result := map[string]any{"closed": true, "disposed": !pendingCleanup(err)}
	if !pendingCleanup(err) {
		return result
	}
	m.mu.Lock()
	id := fmt.Sprintf("%032x", m.next())
	m.retained[id] = err
	m.mu.Unlock()
	result["cleanup"] = id
	return result
}
func (m *manager) reservationCall(ctx context.Context, r Request) (map[string]any, error) {
	if r.Op == "cleanup_status" {
		id, err := tokenField(r.Cleanup)
		if err != nil {
			return invalid("fork_options", err)
		}
		m.mu.Lock()
		cause := m.retained[id]
		m.mu.Unlock()
		err = disposal.Retry(ctx, cause)
		done := !pendingCleanup(cause) && err == nil
		if done {
			m.mu.Lock()
			delete(m.retained, id)
			m.mu.Unlock()
		}
		return map[string]any{"closed": true, "disposed": done}, err
	}
	if r.Op == "fork_reserve" {
		m.mu.Lock()
		b := m.snaps[r.Handle]
		m.mu.Unlock()
		if b == nil {
			return map[string]any{"closed": false}, admission(forklimit.ErrClosed)
		}
		l, err := b.forkLimit().TryAcquire(false)
		if err == forklimit.ErrFull {
			maxForks, occupied := b.forkLimit().Usage()
			return map[string]any{"full": true, "closed": false, "max_forks": maxForks, "occupied_slots": occupied}, nil
		}
		if err != nil {
			return map[string]any{"closed": false}, admission(b.forkLimit().Describe(err))
		}
		id, err := token()
		if err != nil {
			l.Cancel()
			return nil, err
		}
		m.mu.Lock()
		m.reservations[id] = &reservation{base: b, handle: r.Handle, lease: l, stage: "reserved"}
		m.mu.Unlock()
		return map[string]any{"reservation": id, "full": false, "closed": false}, nil
	}
	id, err := tokenField(r.Reservation)
	if err != nil {
		return invalid("fork_options", err)
	}
	m.mu.Lock()
	a := m.reservations[id]
	if a == nil {
		m.mu.Unlock()
		return map[string]any{"closed": false, "disposed": true}, nil
	}
	if a.handle != r.Handle {
		m.mu.Unlock()
		return invalid("fork_options", errors.New("reservation belongs to another Snapshot"))
	}
	if r.Op == "fork_cancel" {
		if a.stage == "reserved" {
			delete(m.reservations, id)
			a.lease.Cancel()
		}
		m.mu.Unlock()
		return map[string]any{"closed": false}, nil
	}
	if a.stage != "exported" {
		m.mu.Unlock()
		return invalid("fork_options", errors.New("handoff has not completed"))
	}
	if r.Op == "handoff_abandon" {
		a.lease.Settle(errors.New("remote child cleanup is not confirmed"))
		m.mu.Unlock()
		return map[string]any{"closed": false}, nil
	}
	m.mu.Unlock()
	cleanup := disposal.RemoveAfter(nil, a.path)
	if cleanup != nil {
		a.lease.TrackCleanup(cleanup)
		return map[string]any{"closed": false}, cleanup
	}
	a.lease.Settle(nil)
	m.mu.Lock()
	if m.reservations[id] == a {
		delete(m.reservations, id)
	}
	m.mu.Unlock()
	return map[string]any{"closed": false, "disposed": true}, nil
}
func (m *manager) cancelReservations(b *baseline) {
	m.mu.Lock()
	defer m.mu.Unlock()
	for id, a := range m.reservations {
		if a.base == b && a.stage == "reserved" {
			a.lease.Cancel()
			delete(m.reservations, id)
		}
	}
}
func (m *manager) claim(r Request, export bool) (*reservation, error) {
	id, err := tokenField(r.Reservation)
	if err != nil {
		return nil, err
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	a := m.reservations[id]
	if a == nil || a.handle != r.Handle || a.stage != "reserved" {
		return nil, forklimit.ErrLease
	}
	a.stage = "starting"
	if !export {
		delete(m.reservations, id)
	}
	return a, nil
}
func (m *manager) fork(ctx context.Context, r Request) (map[string]any, error) {
	var a *reservation
	var err error
	waitctx := ctx
	if len(r.ForkTimeout) != 0 {
		d, e := forklimit.DecodeWait(r.ForkTimeout)
		if e != nil {
			return invalid("fork_options", e)
		}
		if len(r.Reservation) != 0 {
			return invalid("fork_options", errors.New("reserved startup cannot wait for capacity again"))
		}
		var cancel context.CancelFunc
		waitctx, cancel = context.WithTimeout(ctx, d)
		defer cancel()
	}
	if len(r.Reservation) != 0 {
		a, err = m.claim(r, false)
	} else {
		m.mu.Lock()
		b := m.snaps[r.Handle]
		m.mu.Unlock()
		if b == nil {
			return map[string]any{"closed": false}, admission(forklimit.ErrClosed)
		}
		l, e := b.forkLimit().Acquire(waitctx)
		err = e
		a = &reservation{base: b, handle: r.Handle, lease: l}
	}
	if err != nil {
		if a != nil {
			err = a.base.forkLimit().Describe(err)
		}
		return map[string]any{"closed": false}, admission(err)
	}
	b := a.base
	b.mu.RLock()
	defer b.mu.RUnlock()
	if b.closed {
		a.lease.Cancel()
		return map[string]any{"closed": false}, admission(forklimit.ErrClosed)
	}
	if err := a.lease.Activate(); err != nil {
		a.lease.Cancel()
		return invalid("fork_options", err)
	}
	return m.create(ctx, r, b, a.lease)
}
func (m *manager) exportReserved(ctx context.Context, r Request) (map[string]any, error) {
	a, err := m.claim(r, true)
	if err != nil {
		return invalid("fork_options", err)
	}
	id, _ := tokenField(r.Reservation)
	b := a.base
	b.mu.RLock()
	defer b.mu.RUnlock()
	fail := func(err error) (map[string]any, error) {
		settleStartup(a.lease, err)
		m.mu.Lock()
		delete(m.reservations, id)
		m.mu.Unlock()
		return m.retainFailure(err), err
	}
	if b.closed {
		a.lease.Cancel()
		return fail(admission(forklimit.ErrClosed))
	}
	if err := a.lease.Activate(); err != nil {
		a.lease.Cancel()
		return fail(admission(err))
	}
	if err := ctx.Err(); err != nil {
		return fail(err)
	}
	if err := os.Mkdir(r.TransferPath, 0700); err != nil {
		return fail(err)
	}
	a.path = r.TransferPath
	payload := filepath.Join(r.TransferPath, "payload")
	if err := b.owned.Handoff(payload, runtimekind.GuestSHA256); err != nil {
		return fail(disposal.RemoveAfter(err, r.TransferPath))
	}
	m.mu.Lock()
	a.stage = "exported"
	m.mu.Unlock()
	return map[string]any{"lease": id, "transfer_path": payload, "closed": false}, nil
}

func (m *manager) finishConsumed(d *db, handle uint64, result map[string]any, err error) {
	d.settle(err)
	result["disposed"] = d.disposed()
	if !d.disposed() {
		result["cleanup_handle"] = handle
		return
	}
	m.mu.Lock()
	delete(m.dbs, handle)
	m.mu.Unlock()
}
