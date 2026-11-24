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
	"testing"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem/internal/generatedgo"
	"github.com/masahitojp/mariamem/internal/host"
	"github.com/masahitojp/mariamem/internal/nativewire"
	"github.com/masahitojp/mariamem/internal/runtimekind"
)

func encodeControlFrame(kind byte, req, slot uint32, epoch, gen, val uint64, body []byte) []byte {
	out := make([]byte, 37+len(body))
	binary.LittleEndian.PutUint32(out[0:4], uint32(33+len(body)))
	out[4] = kind
	binary.LittleEndian.PutUint32(out[5:9], req)
	binary.LittleEndian.PutUint32(out[9:13], slot)
	binary.LittleEndian.PutUint64(out[13:21], epoch)
	binary.LittleEndian.PutUint64(out[21:29], gen)
	binary.LittleEndian.PutUint64(out[29:37], val)
	copy(out[37:], body)
	return out
}

func startActualGuestWithInject(t *testing.T, ctx context.Context, timeout time.Duration, injectValue uint64) (host.Service, *bytes.Buffer) {
	t.Helper()
	var stderr bytes.Buffer
	runner := func(x nativewire.Execution) <-chan error {
		in := x.Input
		if injectValue != 0 {
			// Request ID 0 causes host readLoop to ignore the unsolicited INJECT REPLY(102).
			prefix := encodeControlFrame(13, 0, 0, x.Epoch, 0, injectValue, nil)
			in = io.MultiReader(bytes.NewReader(prefix), x.Input)
		}
		return generatedgo.StartWireInstance(in, x.Output, x.Stderr, "", x.Restore, x.GuestTiming, x.Failure, x.Epoch, &generatedgo.WireLifecycle{
			Capture:         x.Capture,
			Approval:        x.Approval,
			OnStopped:       x.Stopped,
			BindGuestTiming: x.BindGuestTiming,
		})
	}
	svc, err := host.StartNative(ctx, nil, timeout, &stderr, runtimekind.GuestSHA256, runner)
	if err != nil {
		t.Fatalf("StartNative failed: %v\nstderr:\n%s", err, stderr.String())
	}
	return svc, &stderr
}

func openServiceSQL(t *testing.T, svc host.Service) *sql.DB {
	t.Helper()
	dsn := fmt.Sprintf("root@tcp(127.0.0.1:%d)/test?timeout=5s&readTimeout=5s&writeTimeout=5s", svc.Port())
	pool, err := sql.Open("mysql", dsn)
	if err != nil {
		t.Fatal(err)
	}
	pool.SetMaxOpenConns(1)
	pool.SetMaxIdleConns(1)
	t.Cleanup(func() { _ = pool.Close() })
	return pool
}

// P1 actual-guest regression: when session rollback/cleanup fails (INJECT=1),
// the guest must poison the instance immediately so SnapshotKeep returns no
// root and an unusable/cleanup_failed error, and ordinary Close also reports
// the cleanup failure (both when cleanup fails before Close and during Close).
func TestCleanupFailureActualGuestRejectsSnapshotKeepAndFailsClose(t *testing.T) {
	t.Run("disconnect_before_keep_and_close", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
		defer cancel()
		svc, stderr := startActualGuestWithInject(t, ctx, 0, 1)

		pool := openServiceSQL(t, svc)
		conn, err := pool.Conn(ctx)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := conn.ExecContext(ctx, "CREATE TABLE t_cleanup(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
			t.Fatal(err)
		}
		if _, err := conn.ExecContext(ctx, "BEGIN"); err != nil {
			t.Fatal(err)
		}
		if _, err := conn.ExecContext(ctx, "INSERT INTO t_cleanup VALUES(1)"); err != nil {
			t.Fatal(err)
		}
		// Close client connection with an uncommitted update to trigger THD::cleanup() + INJECT=1.
		_ = conn.Close()
		_ = pool.Close()

		// Wait until the guest reports the cleanup_failed poison to the host.
		deadline := time.Now().Add(5 * time.Second)
		for svc.Failure() == nil && time.Now().Before(deadline) {
			time.Sleep(5 * time.Millisecond)
		}
		if svc.Failure() == nil || !strings.Contains(svc.Failure().Error(), "cleanup_failed") {
			t.Fatalf("expected immediate cleanup_failed failure on host, got %v\nstderr:\n%s", svc.Failure(), stderr.String())
		}

		owned, err := svc.SnapshotKeep(ctx)
		if owned != nil {
			_ = owned.Close()
			t.Fatalf("SnapshotKeep returned non-nil root after cleanup_failed: %v", owned)
		}
		var rej *host.Rejected
		if err == nil || !errors.As(err, &rej) || rej.Code != "unusable" || !strings.Contains(err.Error(), "cleanup_failed") {
			t.Fatalf("expected unusable cleanup_failed from SnapshotKeep, got %v", err)
		}

		closeErr := svc.Close(ctx)
		if closeErr == nil || !strings.Contains(closeErr.Error(), "cleanup_failed") {
			t.Fatalf("expected ordinary Close to report cleanup_failed, got %v\nstderr:\n%s", closeErr, stderr.String())
		}
	})

	t.Run("open_session_fails_during_ordinary_close", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
		defer cancel()
		svc, stderr := startActualGuestWithInject(t, ctx, 0, 1)

		pool := openServiceSQL(t, svc)
		conn, err := pool.Conn(ctx)
		if err != nil {
			t.Fatal(err)
		}
		defer conn.Close()
		if _, err := conn.ExecContext(ctx, "CREATE TABLE t_cleanup2(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
			t.Fatal(err)
		}
		if _, err := conn.ExecContext(ctx, "BEGIN"); err != nil {
			t.Fatal(err)
		}
		if _, err := conn.ExecContext(ctx, "INSERT INTO t_cleanup2 VALUES(2)"); err != nil {
			t.Fatal(err)
		}

		// Keep the session open so rollback runs during ordinary Close (closing==true).
		closeErr := svc.Close(ctx)
		if closeErr == nil || !strings.Contains(closeErr.Error(), "cleanup_failed") {
			t.Fatalf("expected ordinary Close to report cleanup_failed when rollback fails during shutdown, got %v\nstderr:\n%s", closeErr, stderr.String())
		}
	})
}

func rawOverflowSession(t *testing.T, port int, setupSQL ...string) net.Conn {
	t.Helper()
	conn, err := net.DialTimeout("tcp4", fmt.Sprintf("127.0.0.1:%d", port), 5*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	_ = conn.SetDeadline(time.Now().Add(10 * time.Second))

	readPkt := func() []byte {
		var h [4]byte
		if _, err := io.ReadFull(conn, h[:]); err != nil {
			t.Fatalf("read mysql hdr: %v", err)
		}
		n := int(h[0]) | int(h[1])<<8 | int(h[2])<<16
		b := make([]byte, n)
		if _, err := io.ReadFull(conn, b); err != nil {
			t.Fatalf("read mysql body: %v", err)
		}
		return b
	}
	writePkt := func(seq byte, payload []byte) {
		f := make([]byte, 4+len(payload))
		f[0], f[1], f[2], f[3] = byte(len(payload)), byte(len(payload)>>8), byte(len(payload)>>16), seq
		copy(f[4:], payload)
		if _, err := conn.Write(f); err != nil {
			t.Fatalf("write mysql pkt: %v", err)
		}
	}

	// Read greeting, send minimal handshake for database "test".
	_ = readPkt()
	var resp bytes.Buffer
	flags := uint32(1 | 8 | 512 | 32768 | 524288)
	_ = binary.Write(&resp, binary.LittleEndian, flags)
	_ = binary.Write(&resp, binary.LittleEndian, uint32(16*1024*1024))
	resp.WriteByte(45)
	resp.Write(make([]byte, 23))
	resp.WriteString("root\x00\x00test\x00mysql_native_password\x00")
	writePkt(1, resp.Bytes())
	if rep := readPkt(); len(rep) == 0 || rep[0] != 0x00 {
		t.Fatalf("unexpected auth reply: %x", rep)
	}

	for _, q := range setupSQL {
		p := append([]byte{0x03}, []byte(q)...)
		writePkt(0, p)
		if rep := readPkt(); len(rep) == 0 || rep[0] == 0xff {
			t.Fatalf("setup SQL %q failed: %x", q, rep)
		}
	}
	return conn
}

func sendOverflowBurst(conn net.Conn) {
	// Start a slow query, then immediately pipeline >1,048,581 bytes so the
	// guest receive buffer overflows while the worker is executing.
	sleepSQL := append([]byte{0x03}, []byte("SELECT SLEEP(5)")...)
	hdr := []byte{byte(len(sleepSQL)), byte(len(sleepSQL) >> 8), byte(len(sleepSQL) >> 16), 0}
	_, _ = conn.Write(append(hdr, sleepSQL...))

	chunk := bytes.Repeat([]byte("A"), 32768)
	for sent := 0; sent < 1200000; sent += len(chunk) {
		if _, err := conn.Write(chunk); err != nil {
			return
		}
	}
}

// P2 actual-guest regression: an overflow-retiring worker must keep its
// deadline armed through THD::cleanup() until the worker actually exits.
// If cleanup completes within the deadline, peer sessions continue normally;
// if cleanup stalls past the deadline, the instance terminates with deadline.
func TestOverflowCleanupDeadlineActualGuest(t *testing.T) {
	t.Run("cleanup_within_deadline_preserves_peer", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
		defer cancel()
		svc, stderr := startActualGuestWithInject(t, ctx, 2*time.Second, 0)
		defer func() {
			if err := svc.Close(ctx); err != nil {
				t.Errorf("close failed: %v\nstderr:\n%s", err, stderr.String())
			}
		}()

		peer := openServiceSQL(t, svc)
		if _, err := peer.ExecContext(ctx, "CREATE TABLE t_ovf(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
			t.Fatal(err)
		}
		victim := rawOverflowSession(t, svc.Port(), "BEGIN", "INSERT INTO t_ovf VALUES(10)")
		sendOverflowBurst(victim)

		// Wait for victim session to retire; peer stays connected (Active == 1).
		deadline := time.Now().Add(5 * time.Second)
		for svc.Active() > 1 && time.Now().Before(deadline) {
			time.Sleep(10 * time.Millisecond)
		}
		if svc.Failure() != nil {
			t.Fatalf("peer/instance failed on normal overflow cleanup: %v\nstderr:\n%s", svc.Failure(), stderr.String())
		}
		var count int
		if err := peer.QueryRowContext(ctx, "SELECT COUNT(*) FROM t_ovf").Scan(&count); err != nil {
			t.Fatalf("peer query failed after victim overflow rollback: %v", err)
		}
		if count != 0 {
			t.Fatalf("expected uncommitted victim row to be rolled back, got count=%d", count)
		}
		if _, err := peer.ExecContext(ctx, "INSERT INTO t_ovf VALUES(20)"); err != nil {
			t.Fatalf("peer insert failed after victim overflow: %v", err)
		}
	})

	t.Run("cleanup_exceeds_deadline_terminates_instance", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
		defer cancel()
		// INJECT=4 stalls CLEANUP_RESULT (inside THD::cleanup(), after UNREGISTER_THD)
		// on overflowed sessions until poisoned or closing.
		svc, stderr := startActualGuestWithInject(t, ctx, 250*time.Millisecond, 4)

		peer := openServiceSQL(t, svc)
		if _, err := peer.ExecContext(ctx, "CREATE TABLE t_ovf_stall(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
			t.Fatal(err)
		}
		victim := rawOverflowSession(t, svc.Port(), "BEGIN", "INSERT INTO t_ovf_stall VALUES(10)")
		sendOverflowBurst(victim)

		deadline := time.Now().Add(5 * time.Second)
		for svc.Failure() == nil && time.Now().Before(deadline) {
			time.Sleep(10 * time.Millisecond)
		}
		failure := svc.Failure()
		if failure == nil {
			_ = svc.Close(ctx)
			t.Fatalf("expected instance deadline poison when overflow cleanup exceeded 250ms, but instance stayed alive\nstderr:\n%s", stderr.String())
		}
		if !errors.Is(failure, context.DeadlineExceeded) && !strings.Contains(failure.Error(), "deadline") {
			_ = svc.Close(ctx)
			t.Fatalf("expected deadline failure on stalled overflow cleanup, got %v\nstderr:\n%s", failure, stderr.String())
		}
		_ = svc.Close(ctx)
	})
}

// M2 actual-guest regression (#239 / #251): when a client requests a large
// multi-packet response (>64 KiB) and abruptly disconnects while the guest is
// streaming output, the guest must receive peer output EOF, poison the instance
// with peer_output_error, and reject subsequent operations rather than hanging.
func TestMidResponseDisconnectActualGuestPoisonsInstance(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	svc, stderr := startActualGuestWithInject(t, ctx, 0, 0)
	defer func() { _ = svc.Close(ctx) }()

	// Use raw TCP so we can drop the client socket immediately without draining
	// the >64 KiB response stream.
	conn := rawOverflowSession(t, svc.Port())
	query := "SELECT REPEAT('M', 262144), SLEEP(5)"
	payload := append([]byte{0x03}, []byte(query)...)
	hdr := []byte{byte(len(payload)), byte(len(payload) >> 8), byte(len(payload) >> 16), 0}
	if _, err := conn.Write(append(hdr, payload...)); err != nil {
		t.Fatalf("write large query: %v", err)
	}
	// Read only the first few bytes of the response so the guest is actively
	// streaming output packets, then abruptly close the client socket.
	var peek [16]byte
	_ = conn.SetReadDeadline(time.Now().Add(15 * time.Second))
	if _, err := io.ReadFull(conn, peek[:]); err != nil {
		t.Fatalf("read initial response bytes: %v\nstderr:\n%s", err, stderr.String())
	}
	if tcp, ok := conn.(*net.TCPConn); ok {
		_ = tcp.SetLinger(0)
	}
	_ = conn.Close()

	deadline := time.Now().Add(15 * time.Second)
	for svc.Failure() == nil && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	failure := svc.Failure()
	if failure == nil {
		t.Fatalf("expected peer_output_error poison after mid-response disconnect, but instance stayed alive\nstderr:\n%s", stderr.String())
	}
	if !strings.Contains(failure.Error(), "peer_output_error") {
		t.Fatalf("expected peer_output_error failure after mid-response disconnect, got %v\nstderr:\n%s", failure, stderr.String())
	}
}
