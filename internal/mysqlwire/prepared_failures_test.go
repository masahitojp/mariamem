package mysqlwire

import (
	"bytes"
	"encoding/binary"
	"reflect"
	"testing"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

// Test the dispatcher, not just the decoder: rejected bytes must not commit
// cached descriptors, call the engine or leak partial rows.
func TestPreparedEveryTruncatedExecuteRetainsOwnedState(t *testing.T) {
	open := preparedOpen(7)
	open.PreparedOperations = []byte{22, 23, 24, 25, 26}
	s, err := newPreparedSession(open, 1, open.PreparedOperations)
	if err != nil {
		t.Fatal(err)
	}
	id, err := s.registry.Add(7, 91, 1)
	if err != nil {
		t.Fatal(err)
	}
	payload := []byte{0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 8, 128, 255, 255, 255, 255, 255, 255, 255, 255}
	binary.LittleEndian.PutUint32(payload, id)
	calls := 0
	call := func(b []byte, monitor bool) (guest.Result, error) {
		calls++
		req, e := preparedproto.Decode(b)
		if e != nil || req.Operation != 23 || req.Handle != 91 || !monitor {
			t.Fatal(req, e)
		}
		return guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: 7, StatementID: 91, BinaryRows: true, Status: 2, Affected: "0", InsertID: "0"}, nil
	}
	if _, err = s.handle(23, payload, call); err != nil {
		t.Fatal(err)
	}
	before := append([]preparedproto.ParameterType(nil), s.types[id]...)
	for n := 0; n < len(payload); n++ {
		reply, e := s.handle(23, payload[:n], call)
		if e != nil || len(reply) != 1 || len(reply[0]) < 3 || reply[0][0] != 255 || binary.LittleEndian.Uint16(reply[0][1:]) != 1835 {
			t.Fatalf("prefix %d: %x %v", n, reply, e)
		}
		if calls != 1 || !reflect.DeepEqual(before, s.types[id]) {
			t.Fatal("invalid prefix changed ownership", n, calls)
		}
	}
	// Surplus input is equally invalid. No wire error may borrow extra bytes
	// from the next command, or silently retry SQL.
	reply, e := s.handle(23, append(bytes.Clone(payload), 0), call)
	if e != nil || len(reply) != 1 || binary.LittleEndian.Uint16(reply[0][1:]) != 1835 || calls != 1 {
		t.Fatal(reply, e, calls)
	}
	if _, err = s.handle(23, payload, call); err != nil || calls != 2 {
		t.Fatal("following valid EXECUTE", err, calls)
	}
}

func TestPreparedDispatcherRejectsLateResultBeforeReturningAnyPackets(t *testing.T) {
	for _, multi := range []bool{false, true} {
		for _, failure := range []string{"late-cell", "late-owner", "late-more", "transport-generation"} {
			t.Run(failure+map[bool]string{false: "/without-PS_MULTI", true: "/with-PS_MULTI"}[multi], func(t *testing.T) {
				open := preparedOpen(7)
				open.PreparedOperations = []byte{22, 23, 25, 26}
				s, err := newPreparedSession(open, 1, open.PreparedOperations)
				if err != nil {
					t.Fatal(err)
				}
				s.psMulti = multi
				id, err := s.registry.Add(7, 91, 1)
				if err != nil {
					t.Fatal(err)
				}
				p := []byte{0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 3, 0, 7, 0, 0, 0}
				binary.LittleEndian.PutUint32(p, id)
				r, _ := minimalPreparedChain(t)
				r.PreparedVersion = 1
				r.SessionGeneration = 7
				switch failure {
				case "late-cell":
					r.Results[2].Rows[0][0].Hex = "zz"
				case "late-owner":
					r.Results[2].StatementID++
				case "late-more":
					r.Results[len(r.Results)-1].Status |= 8
				case "transport-generation":
					r.SessionGeneration++
				}
				calls := 0
				replies, e := s.handle(23, p, func([]byte, bool) (guest.Result, error) { calls++; return r, nil })
				if e == nil || replies != nil || calls != 1 {
					t.Fatal("partial success or retry", len(replies), e, calls)
				}
			})
		}
	}
}
