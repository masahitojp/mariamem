package mysqlwire

import (
	"encoding/binary"
	"errors"
	"io"
	"net"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

func TestLongDataNoReplyOwnedMappingDeferredErrorAndReset(t *testing.T) {
	open := preparedOpen(7)
	open.PreparedOperations = []byte{22, 23, 24, 25, 26}
	s, err := newPreparedSession(open, 1, open.PreparedOperations)
	if err != nil {
		t.Fatal(err)
	}
	id, _ := s.registry.Add(7, 91, 1)
	calls := 0
	bad := false
	call := func(b []byte, monitor bool) (guest.Result, error) {
		req, e := preparedproto.Decode(b)
		if e != nil {
			t.Fatal(e)
		}
		calls++
		if req.Generation != 7 || req.Handle != 91 || monitor != (req.Operation != 24 && req.Operation != 25) {
			t.Fatal(req, monitor)
		}
		r := guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: 7, Status: 2}
		if req.Operation == 24 && bad {
			r.OK = false
			r.Errno = 1210
			r.SQLState = "HY000"
			r.Error = "Incorrect arguments to mysqld_stmt_send_long_data"
		}
		return r, nil
	}
	chunk := append(le32(id), 0, 0, 'A', 0, 'B')
	for _, b := range [][]byte{nil, {1}, {1, 0, 0, 0, 0}, append(le32(99), 0, 0, 'x')} {
		packets, e := s.handle(24, b, call)
		if e != nil || packets == nil || len(packets) != 0 || calls != 0 {
			t.Fatal("short/unknown LONG_DATA replied/reached guest", packets, e, calls)
		}
	}
	packets, err := s.handle(24, chunk, call)
	if err != nil || packets == nil || len(packets) != 0 || !s.long[id][0] {
		t.Fatal(packets, err)
	}
	// Empty chunk is still present, and no chunk payload is retained in host state.
	if _, err = s.handle(24, chunk[:6], call); err != nil || len(s.long[id]) != 1 {
		t.Fatal(err)
	}
	bad = true
	if packets, err = s.handle(24, append(le32(id), 9, 0, 'x'), call); err != nil || len(packets) != 0 {
		t.Fatal(packets, err)
	}
	before := calls
	body := append(le32(id), 0, 1, 0, 0, 0)
	packets, err = s.handle(23, body, call)
	if err != nil || calls != before || binary.LittleEndian.Uint16(packets[0][1:]) != 1210 {
		t.Fatal("deferred error lost", packets, calls, err)
	}
	if _, err = s.handle(26, le32(id), call); err != nil || len(s.long) != 0 || len(s.longErrors) != 0 {
		t.Fatal("RESET retained stream/error", err)
	}
	bad = false
	if _, err = s.handle(24, chunk, call); err != nil {
		t.Fatal(err)
	}
	if _, err = s.handle(25, le32(id), call); err != nil || len(s.long) != 0 || len(s.longErrors) != 0 {
		t.Fatal("CLOSE retained stream/error", err)
	}
}
func TestLongDataFailedOrMalformedAckIsFatalWithoutInventedReply(t *testing.T) {
	for _, mode := range []string{"transport", "schema", "rows", "unexpected-native-error", "accepted-invalid-index", "spurious-deferred-error"} {
		t.Run(mode, func(t *testing.T) {
			open := preparedOpen(7)
			open.PreparedOperations = []byte{22, 23, 24, 25, 26}
			s, _ := newPreparedSession(open, 1, open.PreparedOperations)
			id, _ := s.registry.Add(7, 91, 1)
			body := append(le32(id), 0, 0, 'x')
			if mode == "accepted-invalid-index" {
				body[4] = 9
			}
			packets, err := s.handle(24, body, func(_ []byte, monitor bool) (guest.Result, error) {
				if monitor {
					t.Fatal("LONG_DATA monitored next packet")
				}
				r := guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: 7, Status: 2}
				switch mode {
				case "transport":
					return guest.Result{}, errors.New("injected failure")
				case "schema":
					r.PreparedVersion = 2
				case "rows":
					r.Rows = [][]*guest.Cell{{}}
				case "spurious-deferred-error":
					r.OK = false
					r.Errno = 1210
					r.SQLState = "HY000"
				case "unexpected-native-error":
					r.OK = false
					r.Errno = 2008
					r.SQLState = "HY000"
				}
				return r, nil
			})
			if err == nil || packets != nil || len(s.long) != 0 {
				t.Fatal("failed ACK became success", packets, err)
			}
		})
	}
}

func TestNoResponseTransportFailureDoesNotLeaveErrorPacket(t *testing.T) {
	for _, op := range []byte{23, 24, 25, 26} {
		server, client := net.Pipe()
		injected := errors.New("injected command failure")
		done := make(chan error, 1)
		go func() {
			w := wire{conn: server, timeout: time.Second}
			done <- w.commandFailure(op, injected)
			server.Close()
		}()
		client.SetReadDeadline(time.Now().Add(2 * time.Second))
		if op == 24 || op == 25 {
			var b [4]byte
			n, err := client.Read(b[:])
			if n != 0 || !errors.Is(err, io.EOF) {
				t.Fatal("invented no-response error packet", op, n, err)
			}
		} else {
			w := wire{conn: client, timeout: time.Second}
			b, err := w.read(false)
			if err != nil || len(b) < 3 || b[0] != 255 || binary.LittleEndian.Uint16(b[1:]) != 2013 {
				t.Fatal(op, b, err)
			}
		}
		if err := <-done; err != injected {
			t.Fatal(err)
		}
		client.Close()
	}
}
