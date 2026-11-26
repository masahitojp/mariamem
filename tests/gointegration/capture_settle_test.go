//go:build integration

package gointegration

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo"
	"github.com/masahitojp/mariamem/internal/host"
	"github.com/masahitojp/mariamem/internal/nativewire"
	"github.com/masahitojp/mariamem/internal/runtimekind"
)

// ackHoldingFilter wraps Execution.Input to intercept and hold kindAck (kind=3)
// frames while forwarding TRY_CAPTURE, STATS, and all other control frames
// immediately to the real guest.
type ackHoldingFilter struct {
	mu       sync.Mutex
	cond     *sync.Cond
	holdAck  bool
	heldAcks [][]byte
	outQueue [][]byte
	eof      bool
	readErr  error
	cur      []byte

	ackHeldCh   chan struct{}
	fenceSeenCh chan struct{}
	statsSeenCh chan struct{}
}

func newAckHoldingFilter(src io.Reader) *ackHoldingFilter {
	f := &ackHoldingFilter{
		ackHeldCh:   make(chan struct{}, 1),
		fenceSeenCh: make(chan struct{}, 4),
		statsSeenCh: make(chan struct{}, 4),
	}
	f.cond = sync.NewCond(&f.mu)
	go f.pump(src)
	return f
}

func (f *ackHoldingFilter) pump(src io.Reader) {
	var lenBuf [4]byte
	for {
		if _, err := io.ReadFull(src, lenBuf[:]); err != nil {
			f.mu.Lock()
			f.eof = true
			f.readErr = err
			f.cond.Broadcast()
			f.mu.Unlock()
			return
		}
		n := binary.LittleEndian.Uint32(lenBuf[:])
		raw := make([]byte, 4+n)
		copy(raw[:4], lenBuf[:])
		if _, err := io.ReadFull(src, raw[4:]); err != nil {
			f.mu.Lock()
			f.eof = true
			f.readErr = err
			f.cond.Broadcast()
			f.mu.Unlock()
			return
		}
		kind := raw[4]
		f.mu.Lock()
		switch kind {
		case 3: // kindAck
			if f.holdAck {
				f.heldAcks = append(f.heldAcks, raw)
				select {
				case f.ackHeldCh <- struct{}{}:
				default:
				}
				f.mu.Unlock()
				continue
			}
		case 11: // kindCaptureFence (TRY_CAPTURE)
			select {
			case f.fenceSeenCh <- struct{}{}:
			default:
			}
		case 7: // kindStats
			select {
			case f.statsSeenCh <- struct{}{}:
			default:
			}
		}
		f.outQueue = append(f.outQueue, raw)
		f.cond.Broadcast()
		f.mu.Unlock()
	}
}

func (f *ackHoldingFilter) SetHoldAck(hold bool) {
	f.mu.Lock()
	f.holdAck = hold
	if !hold && len(f.heldAcks) > 0 {
		f.outQueue = append(f.outQueue, f.heldAcks...)
		f.heldAcks = nil
		f.cond.Broadcast()
	}
	f.mu.Unlock()
}

func (f *ackHoldingFilter) Read(p []byte) (int, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	for len(f.cur) == 0 && len(f.outQueue) == 0 {
		if f.eof {
			if f.readErr != nil {
				return 0, f.readErr
			}
			return 0, io.EOF
		}
		f.cond.Wait()
	}
	if len(f.cur) == 0 {
		f.cur = f.outQueue[0]
		f.outQueue = f.outQueue[1:]
	}
	n := copy(p, f.cur)
	f.cur = f.cur[n:]
	return n, nil
}

// Acceptance Criterion 1 (real r6 guest): hold ACK after UPDATE OK reaches the
// client so guest stays in FLUSHING when Snapshot(Rollback:true) starts; once
// ACK is released, the exact same Snapshot call succeeds and Fork observes the
// pre-transaction value 42.
func TestSnapshotRollbackActualGuestHeldAckSucceedsAndPreservesPreTxValue(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	var stderr bytes.Buffer
	filterCh := make(chan *ackHoldingFilter, 1)
	runner := func(x nativewire.Execution) <-chan error {
		flt := newAckHoldingFilter(x.Input)
		filterCh <- flt
		return generatedgo.StartWireInstance(flt, x.Output, x.Stderr, "", x.Restore, x.GuestTiming, x.Failure, x.Epoch, &generatedgo.WireLifecycle{
			Capture:         x.Capture,
			Approval:        x.Approval,
			OnStopped:       x.Stopped,
			BindGuestTiming: x.BindGuestTiming,
		})
	}
	svc, err := host.StartNative(ctx, nil, 0, &stderr, runtimekind.GuestSHA256, runner)
	if err != nil {
		t.Fatalf("StartNative failed: %v\nstderr:\n%s", err, stderr.String())
	}
	defer func() {
		cctx, ccancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer ccancel()
		_ = svc.Close(cctx)
	}()
	flt := <-filterCh

	pool := openServiceSQL(t, svc)
	conn, err := pool.Conn(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	for _, q := range []string{
		"CREATE TABLE shutdown_items(id INT PRIMARY KEY, value INT) ENGINE=InnoDB",
		"INSERT INTO shutdown_items VALUES(1, 42)",
		"SET GLOBAL innodb_fast_shutdown=2",
		"BEGIN",
	} {
		if _, err := conn.ExecContext(ctx, q); err != nil {
			t.Fatal(err)
		}
	}

	// Hold the ACK for the UPDATE OK packet so the client receives OK while the
	// real r6 guest stays in FLUSHING.
	flt.SetHoldAck(true)
	if _, err := conn.ExecContext(ctx, "UPDATE shutdown_items SET value=99"); err != nil {
		t.Fatal(err)
	}
	select {
	case <-flt.ackHeldCh:
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for UPDATE ACK to be intercepted")
	}

	type snapResult struct {
		owned    bool
		consumed bool
		err      error
		forkVal  int
	}
	resCh := make(chan snapResult, 1)
	go func() {
		owned, consumed, err := svc.SnapshotHeap(ctx, true)
		if err != nil || owned == nil {
			if owned != nil {
				_ = owned.Close()
			}
			resCh <- snapResult{owned != nil, consumed, err, -1}
			return
		}
		defer owned.Close()
		var forkStderr bytes.Buffer
		forkSvc, err := host.StartGenerated(ctx, owned, 0, &forkStderr)
		if err != nil {
			resCh <- snapResult{true, consumed, fmt.Errorf("fork start failed: %w\n%s", err, forkStderr.String()), -1}
			return
		}
		defer func() {
			cctx, ccancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer ccancel()
			_ = forkSvc.Close(cctx)
		}()
		fpool := openServiceSQL(t, forkSvc)
		var val int
		err = fpool.QueryRowContext(ctx, "SELECT value FROM shutdown_items WHERE id=1").Scan(&val)
		resCh <- snapResult{true, consumed, err, val}
	}()

	// Wait until the first TRY_CAPTURE fence + STATS ran while ACK was still held
	// (confirming the guest saw FLUSHING and rejected the first fence with busy).
	select {
	case <-flt.fenceSeenCh:
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for first TRY_CAPTURE fence")
	}
	select {
	case <-flt.statsSeenCh:
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for STATS after busy rejection")
	}

	// Release the held ACK; the same SnapshotHeap call must settle and succeed.
	flt.SetHoldAck(false)
	res := <-resCh
	if !res.owned || !res.consumed || res.err != nil {
		t.Fatalf("expected held-ACK SnapshotHeap + Fork to succeed, got %+v\nstderr:\n%s", res, stderr.String())
	}
	if res.forkVal != 42 {
		t.Fatalf("expected rolled-back value 42 in Fork, got %d", res.forkVal)
	}
}

type postWriteHoldListener struct {
	net.Listener
	holdNextWrite atomic.Bool
	writtenCh     chan struct{}
	releaseCh     chan struct{}
}

func (l *postWriteHoldListener) Accept() (net.Conn, error) {
	c, err := l.Listener.Accept()
	if err != nil {
		return nil, err
	}
	return &postWriteHoldConn{Conn: c, parent: l}, nil
}

type postWriteHoldConn struct {
	net.Conn
	parent *postWriteHoldListener
}

func (c *postWriteHoldConn) Write(p []byte) (int, error) {
	n, err := c.Conn.Write(p)
	if err == nil && c.parent.holdNextWrite.CompareAndSwap(true, false) {
		// Response bytes have ALREADY been written to the TCP socket (so the SQL
		// client receives OK and returns from ExecContext), while relay.go has NOT
		// returned from c.Write yet (outBytes > 0, ackTarget/kindAck not updated).
		select {
		case c.parent.writtenCh <- struct{}{}:
		default:
		}
		<-c.parent.releaseCh
	}
	return n, err
}

// P1 regression (real r6 guest): client finishes reading UPDATE OK from TCP
// while relay writer has NOT yet returned from conn.Write (so host outBytes > 0
// and kindAck has not been sent yet). Snapshot(Rollback:true) started in that
// exact state must settle once the writer resumes and Fork must observe 42.
func TestSnapshotRollbackActualGuestPostWritePositiveOutBytesSucceeds(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	var stderr bytes.Buffer
	filterCh := make(chan *ackHoldingFilter, 1)
	runner := func(x nativewire.Execution) <-chan error {
		// Observe TRY_CAPTURE / STATS without holding ACK at the guest pipe.
		flt := newAckHoldingFilter(x.Input)
		filterCh <- flt
		return generatedgo.StartWireInstance(flt, x.Output, x.Stderr, "", x.Restore, x.GuestTiming, x.Failure, x.Epoch, &generatedgo.WireLifecycle{
			Capture:         x.Capture,
			Approval:        x.Approval,
			OnStopped:       x.Stopped,
			BindGuestTiming: x.BindGuestTiming,
		})
	}
	b, err := nativewire.Start(ctx, nativewire.Config{
		Runner: runner,
		Build:  runtimekind.GuestSHA256,
		Stderr: &stderr,
	})
	if err != nil {
		t.Fatalf("nativewire.Start failed: %v\nstderr:\n%s", err, stderr.String())
	}
	defer func() {
		cctx, ccancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer ccancel()
		_ = b.Close(cctx)
	}()
	rawLis, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	lis := &postWriteHoldListener{
		Listener:  rawLis,
		writtenCh: make(chan struct{}, 1),
		releaseCh: make(chan struct{}),
	}
	if err := b.Serve(lis); err != nil {
		_ = rawLis.Close()
		t.Fatal(err)
	}
	flt := <-filterCh

	dsn := fmt.Sprintf("root@tcp(127.0.0.1:%d)/test?timeout=5s&readTimeout=5s&writeTimeout=5s", b.Port())
	pool, err := sql.Open("mysql", dsn)
	if err != nil {
		t.Fatal(err)
	}
	pool.SetMaxOpenConns(1)
	pool.SetMaxIdleConns(1)
	defer pool.Close()
	conn, err := pool.Conn(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()

	for _, q := range []string{
		"CREATE TABLE shutdown_items(id INT PRIMARY KEY, value INT) ENGINE=InnoDB",
		"INSERT INTO shutdown_items VALUES(1, 42)",
		"SET GLOBAL innodb_fast_shutdown=2",
		"BEGIN",
	} {
		if _, err := conn.ExecContext(ctx, q); err != nil {
			t.Fatal(err)
		}
	}

	// Arm post-Write hold: UPDATE OK reaches the SQL client over TCP, then
	// relay.go pauses BEFORE releasing outBytes or sending kindAck.
	lis.holdNextWrite.Store(true)
	if _, err := conn.ExecContext(ctx, "UPDATE shutdown_items SET value=99"); err != nil {
		close(lis.releaseCh)
		t.Fatal(err)
	}
	select {
	case <-lis.writtenCh:
	case <-time.After(5 * time.Second):
		close(lis.releaseCh)
		t.Fatal("timed out waiting for post-Write hold")
	}

	type snapResult struct {
		owned    bool
		consumed bool
		err      error
		forkVal  int
	}
	resCh := make(chan snapResult, 1)
	go func() {
		owned, consumed, err := b.SnapshotHeap(ctx, true)
		if err != nil || owned == nil {
			if owned != nil {
				_ = owned.Close()
			}
			resCh <- snapResult{owned != nil, consumed, err, -1}
			return
		}
		defer owned.Close()
		var forkStderr bytes.Buffer
		forkSvc, err := host.StartGenerated(ctx, owned, 0, &forkStderr)
		if err != nil {
			resCh <- snapResult{true, consumed, fmt.Errorf("fork start failed: %w\n%s", err, forkStderr.String()), -1}
			return
		}
		defer func() {
			cctx, ccancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer ccancel()
			_ = forkSvc.Close(cctx)
		}()
		fpool := openServiceSQL(t, forkSvc)
		var val int
		err = fpool.QueryRowContext(ctx, "SELECT value FROM shutdown_items WHERE id=1").Scan(&val)
		resCh <- snapResult{true, consumed, err, val}
	}()

	// Wait until fence #1 + STATS ran while relay writer was still paused with outBytes > 0.
	select {
	case <-flt.fenceSeenCh:
	case <-time.After(5 * time.Second):
		close(lis.releaseCh)
		t.Fatal("timed out waiting for first TRY_CAPTURE fence")
	}
	select {
	case <-flt.statsSeenCh:
	case <-time.After(5 * time.Second):
		close(lis.releaseCh)
		t.Fatal("timed out waiting for STATS while outBytes > 0")
	}

	// Resume relay writer; the exact same SnapshotHeap call must succeed and Fork must see 42.
	close(lis.releaseCh)
	res := <-resCh
	if !res.owned || !res.consumed || res.err != nil {
		t.Fatalf("expected post-Write outBytes>0 SnapshotHeap + Fork to succeed, got %+v\nstderr:\n%s", res, stderr.String())
	}
	if res.forkVal != 42 {
		t.Fatalf("expected rolled-back value 42 in Fork, got %d", res.forkVal)
	}
}

// Acceptance Criterion 2 (real r6 guest): genuinely busy sessions (long SQL,
// mid-multi-result, stalled host Write) return non-consuming ErrBusy promptly,
// and Rollback:false with an open transaction returns non-consuming ErrTransactionActive.
func TestSnapshotActualGuestBusyMultiResultStalledWriteAndTransactionActive(t *testing.T) {
	t.Run("long_sql_busy", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
		defer cancel()
		db, err := mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			t.Fatal(err)
		}
		defer db.Close()

		pool, err := sql.Open("mysql", db.DSN())
		if err != nil {
			t.Fatal(err)
		}
		defer pool.Close()

		done := make(chan error, 1)
		go func() {
			var v int
			done <- pool.QueryRowContext(ctx, "SELECT SLEEP(3)").Scan(&v)
		}()
		// Give SLEEP(3) time to enter EXECUTING on the guest.
		time.Sleep(100 * time.Millisecond)

		start := time.Now()
		snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{Rollback: true})
		elapsed := time.Since(start)
		if snap != nil {
			_ = snap.Close()
			t.Fatal("Snapshot succeeded during active SLEEP(3)")
		}
		var hostErr *mariamem.HostError
		if !errors.Is(err, mariamem.ErrBusy) || !errors.As(err, &hostErr) || hostErr.Closed || db.Closed() {
			t.Fatalf("expected non-consuming ErrBusy during SLEEP(3), got %v", err)
		}
		if message := err.Error(); !strings.Contains(message, "Wait for active SQL to finish") ||
			!strings.Contains(message, "If results are unread") {
			t.Fatalf("expected guidance for active SQL and conditional guidance for unread results, got %q", message)
		}
		if elapsed > time.Second {
			t.Fatalf("long SQL Snapshot waited too long: %v", elapsed)
		}
		if err := <-done; err != nil {
			t.Fatalf("SLEEP(3) failed after non-consuming busy: %v", err)
		}
	})

	t.Run("multi_result_mid_flight_busy", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
		defer cancel()
		db, err := mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			t.Fatal(err)
		}
		defer db.Close()

		dsn := db.DSN() + "&multiStatements=true"
		pool, err := sql.Open("mysql", dsn)
		if err != nil {
			t.Fatal(err)
		}
		defer pool.Close()

		// Result set 1 ("SELECT 1") is written and delivered immediately while
		// statement 2 ("SELECT SLEEP(3)") is still executing on the guest.
		rows, err := pool.QueryContext(ctx, "SELECT 1; SELECT SLEEP(3)")
		if err != nil {
			t.Fatal(err)
		}
		defer rows.Close()
		if !rows.Next() {
			t.Fatalf("expected first result row, err=%v", rows.Err())
		}
		var first int
		if err := rows.Scan(&first); err != nil || first != 1 {
			t.Fatalf("first result scan: val=%d err=%v", first, err)
		}

		nextDone := make(chan bool, 1)
		go func() {
			nextDone <- rows.NextResultSet()
		}()
		time.Sleep(100 * time.Millisecond)

		start := time.Now()
		snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{Rollback: true})
		elapsed := time.Since(start)
		if snap != nil {
			_ = snap.Close()
			t.Fatal("Snapshot succeeded mid-multi-result")
		}
		var hostErr *mariamem.HostError
		if !errors.Is(err, mariamem.ErrBusy) || !errors.As(err, &hostErr) || hostErr.Closed || db.Closed() {
			t.Fatalf("expected non-consuming ErrBusy mid-multi-result, got %v", err)
		}
		if elapsed > time.Second {
			t.Fatalf("mid-multi-result Snapshot waited too long: %v", elapsed)
		}
		<-nextDone
	})

	t.Run("stalled_host_write_busy", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
		defer cancel()
		db, err := mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			t.Fatal(err)
		}
		defer db.Close()

		setup, err := sql.Open("mysql", db.DSN())
		if err != nil {
			t.Fatal(err)
		}
		for _, q := range []string{
			"CREATE TABLE big_stalled(id INT PRIMARY KEY, body LONGTEXT) ENGINE=InnoDB",
			"INSERT INTO big_stalled VALUES (1, REPEAT('a', 524288)), (2, REPEAT('b', 524288)), (3, REPEAT('c', 524288)), (4, REPEAT('d', 524288)), (5, REPEAT('e', 524288)), (6, REPEAT('f', 524288)), (7, REPEAT('g', 524288)), (8, REPEAT('h', 524288))",
		} {
			if _, err := setup.ExecContext(ctx, q); err != nil {
				setup.Close()
				t.Fatal(err)
			}
		}
		_ = setup.Close()
		if err := db.WaitDisconnected(ctx); err != nil {
			t.Fatal(err)
		}

		// go-sql-driver/mysql reads row packets lazily in rows.Next(); leaving a
		// 4 MiB result set unread fills the loopback buffer and stalls host Write.
		reader, err := sql.Open("mysql", db.DSN())
		if err != nil {
			t.Fatal(err)
		}
		defer reader.Close()

		conn, err := reader.Conn(ctx)
		if err != nil {
			t.Fatal(err)
		}
		defer conn.Close()

		peerPool, err := sql.Open("mysql", db.DSN())
		if err != nil {
			t.Fatal(err)
		}
		defer peerPool.Close()
		peerPool.SetMaxIdleConns(0)
		peer, err := peerPool.Conn(ctx)
		if err != nil {
			t.Fatal(err)
		}
		defer peer.Close()

		rows, err := conn.QueryContext(ctx, "SELECT id, body FROM big_stalled")
		if err != nil {
			t.Fatal(err)
		}
		defer rows.Close()
		time.Sleep(100 * time.Millisecond)

		peerCtx, cancelPeer := context.WithTimeout(ctx, 2*time.Second)
		defer cancelPeer()
		var peerValue int
		if err := peer.QueryRowContext(peerCtx, "SELECT 1").Scan(&peerValue); err != nil || peerValue != 1 {
			t.Fatalf("peer SQL while first connection has unread output: value=%d err=%v", peerValue, err)
		}
		// With no idle pool slots, closing this connection sends COM_QUIT.
		if err := peer.Close(); err != nil {
			t.Fatal(err)
		}
		if err := peerPool.QueryRowContext(peerCtx, "SELECT 2").Scan(&peerValue); err != nil || peerValue != 2 {
			t.Fatalf("replacement peer SQL after disconnect: value=%d err=%v", peerValue, err)
		}

		start := time.Now()
		snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{Rollback: true})
		elapsed := time.Since(start)
		if snap != nil {
			_ = snap.Close()
			t.Fatal("Snapshot succeeded while host Write was stalled")
		}
		var hostErr *mariamem.HostError
		if !errors.Is(err, mariamem.ErrBusy) || !errors.As(err, &hostErr) || hostErr.Closed || db.Closed() {
			t.Fatalf("expected non-consuming ErrBusy while host Write is stalled, got %v", err)
		}
		if elapsed > time.Second {
			t.Fatalf("stalled host Write Snapshot waited too long: %v", elapsed)
		}
		for _, hint := range []string{"The source database is still usable", "read them to completion or close the rows", "before retrying"} {
			if !strings.Contains(err.Error(), hint) {
				t.Errorf("missing guidance %q in %q", hint, err)
			}
		}
		if err := rows.Close(); err != nil {
			t.Fatal(err)
		}
		var n int
		if err := conn.QueryRowContext(ctx, "SELECT COUNT(*) FROM big_stalled").Scan(&n); err != nil || n != 8 {
			t.Fatalf("source unusable after stalled-Write ErrBusy: n=%d err=%v", n, err)
		}

		retried, err := db.Snapshot(ctx, mariamem.SnapshotOptions{Rollback: true})
		if err != nil {
			t.Fatalf("Snapshot retry after closing rows: %v", err)
		}
		defer retried.Close()
		fork, err := retried.Fork(ctx)
		if err != nil {
			t.Fatal(err)
		}
		defer fork.Close()
		forkClient, err := sql.Open("mysql", fork.DSN())
		if err != nil {
			t.Fatal(err)
		}
		defer forkClient.Close()
		var got int
		if err := forkClient.QueryRowContext(ctx, "SELECT COUNT(*) FROM big_stalled").Scan(&got); err != nil || got != n {
			t.Fatalf("Fork after Snapshot retry: expected %d rows, got %d, err=%v", n, got, err)
		}
	})

	t.Run("open_tx_rollback_false_transaction_active", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
		defer cancel()
		db, err := mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			t.Fatal(err)
		}
		defer db.Close()

		pool, err := sql.Open("mysql", db.DSN())
		if err != nil {
			t.Fatal(err)
		}
		defer pool.Close()
		conn, err := pool.Conn(ctx)
		if err != nil {
			t.Fatal(err)
		}
		defer conn.Close()

		for _, q := range []string{
			"CREATE TABLE tx_guard(id INT PRIMARY KEY, v INT) ENGINE=InnoDB",
			"INSERT INTO tx_guard VALUES (1, 10)",
			"BEGIN",
			"UPDATE tx_guard SET v=20 WHERE id=1",
		} {
			if _, err := conn.ExecContext(ctx, q); err != nil {
				t.Fatal(err)
			}
		}

		// Immediately call Rollback:false Snapshot without sleep or retry.
		snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{Rollback: false})
		if snap != nil {
			_ = snap.Close()
			t.Fatal("Rollback:false Snapshot succeeded with open transaction")
		}
		var hostErr *mariamem.HostError
		if !errors.Is(err, mariamem.ErrTransactionActive) || !errors.As(err, &hostErr) || hostErr.Closed || db.Closed() {
			t.Fatalf("expected non-consuming ErrTransactionActive, got %v", err)
		}
	})
}
