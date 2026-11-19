package host

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"net"
	"reflect"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/guest"
)

// keepGuest records the private session's framed calls and answers each from
// reply; a nil reply drops the transport. A missing capture makes KeepRoot fail after the global read lock, so
// lock release and session close ordering are observable without a runtime.
func keepGuest(t *testing.T, reply func(op byte, sql string) map[string]any) (*guest.Process, func() []string) {
	t.Helper()
	childIn, in := io.Pipe()
	out, childOut := io.Pipe()
	completed := make(chan error, 1)
	var mu sync.Mutex
	var calls []string
	go func() {
		defer childIn.Close()
		defer childOut.Close()
		send := func(id uint32, result map[string]any) {
			b, _ := json.Marshal(map[string]any{"request_id": id, "result": result})
			_ = binary.Write(childOut, binary.LittleEndian, uint32(len(b)))
			_, _ = childOut.Write(b)
		}
		send(0, map[string]any{"ready": true, "api_version": 2, "max_sessions": 4, "snapshot_version": 1})
		for {
			var n uint32
			if err := binary.Read(childIn, binary.LittleEndian, &n); err != nil || n == 0 || n >= 0xfffffffe {
				break
			}
			packet := make([]byte, n)
			if _, err := io.ReadFull(childIn, packet); err != nil {
				break
			}
			op, sql := packet[0], string(packet[9:])
			mu.Lock()
			calls = append(calls, string('0'+op)+":"+sql)
			mu.Unlock()
			result := reply(op, sql)
			if result == nil {
				break // drop the transport without replying
			}
			send(binary.LittleEndian.Uint32(packet[1:]), result)
		}
		completed <- nil
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	p, err := guest.Connect(ctx, in, out, completed, nil, io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = p.AbortAndWait(errors.New("test cleanup")) })
	return p, func() []string { mu.Lock(); defer mu.Unlock(); return append([]string(nil), calls...) }
}

func TestSnapshotKeepGlobalReadLockReleaseAndSessionCleanup(t *testing.T) {
	const (
		open     = "1:"
		timeout  = "2:SET SESSION lock_wait_timeout=0"
		recover  = "2:XA RECOVER"
		ftwrl    = "2:FLUSH TABLES WITH READ LOCK"
		ckpt     = "2:SET GLOBAL innodb_log_checkpoint_now=ON"
		unlock   = "2:UNLOCK TABLES"
		closeOp  = "3:"
		lockText = "Lock wait timeout exceeded; try restarting transaction"
	)
	for _, tc := range []struct {
		name         string
		ftwrlErrno   int
		unlockErrno  int
		notClosed    bool
		calls        []string
		code, detail string
		reserved     bool
		failed       bool
	}{
		// A LOCK TABLES WRITE holder: nothing was acquired, so no UNLOCK.
		{name: "write-holder", ftwrlErrno: 1205, calls: []string{open, timeout, recover, ftwrl, closeOp}, code: "busy"},
		// Any failure after the lock still releases it before closing.
		{name: "cut-failure", calls: []string{open, timeout, recover, ftwrl, ckpt, unlock, closeOp}, detail: "running root cut is unsupported"},
		{name: "unlock-failure", unlockErrno: 1064, calls: []string{open, timeout, recover, ftwrl, ckpt, unlock, closeOp}, detail: `"UNLOCK TABLES": errno 1064`},
		// An unconfirmed close keeps the slot reserved; the error is reported.
		{name: "close-failure", notClosed: true, calls: []string{open, timeout, recover, ftwrl, ckpt, unlock, closeOp}, detail: "snapshot keep session did not close", reserved: true},
		{name: "unlock-and-close-failure", unlockErrno: 1064, notClosed: true, calls: []string{open, timeout, recover, ftwrl, ckpt, unlock, closeOp}, detail: "snapshot keep session did not close", reserved: true, failed: true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			p, calls := keepGuest(t, func(op byte, sql string) map[string]any {
				switch {
				case op == 3:
					return map[string]any{"closed": !tc.notClosed}
				case sql == "FLUSH TABLES WITH READ LOCK" && tc.ftwrlErrno != 0:
					return map[string]any{"errno": tc.ftwrlErrno, "sqlstate": "HY000", "error": lockText}
				case sql == "UNLOCK TABLES" && tc.unlockErrno != 0:
					return map[string]any{"errno": tc.unlockErrno, "sqlstate": "42000", "error": "syntax"}
				}
				return map[string]any{"ok": true}
			})
			s := &Server{Guest: p, listener: unusedListener{}, clients: map[net.Conn]*session{}, slots: make([]bool, 2), build: "test-build"}
			owned, err := s.SnapshotKeep(context.Background())
			if owned != nil || err == nil {
				t.Fatalf("owned=%v err=%v", owned, err)
			}
			var rejected *Rejected
			if tc.code != "" && (!errors.As(err, &rejected) || rejected.Code != tc.code) {
				t.Fatalf("code: %v", err)
			}
			if tc.detail != "" && !strings.Contains(err.Error(), tc.detail) {
				t.Fatalf("lost detail %q: %v", tc.detail, err)
			}
			if got := calls(); !reflect.DeepEqual(got, tc.calls) {
				t.Fatalf("calls %q, want %q", got, tc.calls)
			}
			if s.slots[0] != tc.reserved || s.slots[1] {
				t.Fatalf("slots %v, reserved=%v", s.slots, tc.reserved)
			}
			if s.closing || (p.Err() != nil) != tc.failed {
				t.Fatalf("unexpected source state: closing=%v err=%v", s.closing, p.Err())
			}
			if tc.unlockErrno != 0 && !tc.notClosed {
				reply, err := p.Call(context.Background(), 2, 1, []byte("INSERT INTO items VALUES (1)"))
				if err != nil || !reply.OK {
					t.Fatalf("write after confirmed session closure: reply=%v err=%v", reply, err)
				}
			}
			if tc.failed {
				if !strings.Contains(err.Error(), `"UNLOCK TABLES": errno 1064`) {
					t.Fatalf("lost unlock failure: %v", err)
				}
				if _, err := p.Call(context.Background(), 2, 1, []byte("INSERT INTO items VALUES (1)")); err == nil {
					t.Fatal("write reached the failed guest")
				}
				owned, err := s.SnapshotKeep(context.Background())
				if owned != nil || !errors.As(err, &rejected) || rejected.Code != "unusable" {
					t.Fatalf("retry on failed guest: owned=%v err=%v", owned, err)
				}
				if got := calls(); !reflect.DeepEqual(got, tc.calls) {
					t.Fatalf("failed guest received another command: %q", got)
				}
			}
		})
	}
}

// Open failures: a refusal is a confirmed absence of a session, so the slot is
// released and repeated refusals never exhaust capacity. A lost reply leaves the
// session state unknown, so the slot stays reserved (the instance has failed).
func TestSnapshotKeepSessionOpenFailure(t *testing.T) {
	for _, tc := range []struct {
		name     string
		reply    map[string]any
		reserved bool
		failed   bool
		detail   string
	}{
		{name: "refused", reply: map[string]any{"ok": false, "errno": 1049, "error": "Unknown database 'test'"}, detail: "errno 1049: Unknown database 'test'"},
		{name: "opened-with-error", reply: map[string]any{"ok": true, "errno": 1105, "error": "warning"}, detail: "errno 1105"},
		{name: "no-reply", reply: nil, reserved: true, failed: true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			p, calls := keepGuest(t, func(op byte, sql string) map[string]any {
				if op == 1 {
					return tc.reply
				}
				return map[string]any{"ok": true, "closed": true}
			})
			s := &Server{Guest: p, listener: unusedListener{}, clients: map[net.Conn]*session{}, slots: make([]bool, 2), build: "test-build"}
			attempts := 1
			if !tc.reserved {
				attempts = 3 * len(s.slots) // more than capacity
			}
			for i := 0; i < attempts; i++ {
				owned, err := s.SnapshotKeep(context.Background())
				if owned != nil || err == nil {
					t.Fatalf("attempt %d: owned=%v err=%v", i, owned, err)
				}
				var rejected *Rejected
				if errors.As(err, &rejected) && rejected.Code == "capacity" {
					t.Fatalf("attempt %d leaked a slot: %v", i, err)
				}
				if !strings.Contains(err.Error(), tc.detail) {
					t.Fatalf("lost detail %q: %v", tc.detail, err)
				}
			}
			if s.slots[0] != tc.reserved || s.slots[1] {
				t.Fatalf("slots %v, reserved=%v", s.slots, tc.reserved)
			}
			if (p.Err() != nil) != tc.failed {
				t.Fatalf("instance failure %v, want %v", p.Err(), tc.failed)
			}
			if tc.name == "opened-with-error" {
				if got := calls(); len(got) != 2*attempts || got[1] != "3:" {
					t.Fatalf("opened session was not closed: %q", got)
				}
			}
		})
	}
}
