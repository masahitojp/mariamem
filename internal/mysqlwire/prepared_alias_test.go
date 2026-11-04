package mysqlwire

import (
	"bytes"
	"encoding/binary"
	"errors"
	"testing"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

type aliasTestEngine struct {
	generation     uint32
	next           uint32
	requests       []preparedproto.Request
	prepareFailure string
}

func (e *aliasTestEngine) call(b []byte, monitor bool) (guest.Result, error) {
	req, err := preparedproto.Decode(b)
	if err != nil {
		return guest.Result{}, err
	}
	e.requests = append(e.requests, req)
	if req.Generation != e.generation || monitor != (req.Operation != 24 && req.Operation != 25) {
		return guest.Result{}, errors.New("wrong generation or command monitoring")
	}
	r := guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: e.generation, Status: 2, Affected: "0", InsertID: "0"}
	switch req.Operation {
	case 22:
		if e.prepareFailure == "transport" {
			return guest.Result{}, errors.New("prepare transport")
		}
		if e.prepareFailure == "sql" {
			r.OK = false
			r.Errno = 1064
			r.SQLState = "42000"
			r.Error = "prepare SQL failure"
			return r, nil
		}
		e.next++
		r.StatementID = e.next
		r.ParamCount = 1
		r.Parameters = []guest.Column{preparedParameter()}
		if e.prepareFailure == "metadata" {
			r.Rows = [][]*guest.Cell{{}}
		}
	case 23:
		r.StatementID = req.Handle
		r.BinaryRows = true
	case 24:
		if binary.LittleEndian.Uint16(req.Payload) >= 1 {
			r.OK = false
			r.Errno = 1210
			r.SQLState = "HY000"
			r.Error = "invalid long-data parameter"
		}
	}
	return r, nil
}
func aliasTestSession(t *testing.T, generation uint32) (*preparedSession, *aliasTestEngine) {
	t.Helper()
	open := preparedOpen(generation)
	open.PreparedOperations = []byte{22, 23, 24, 25, 26}
	s, err := newPreparedSession(open, 1, open.PreparedOperations)
	if err != nil {
		t.Fatal(err)
	}
	return s, &aliasTestEngine{generation: generation, next: 90}
}
func aliasPrepare(t *testing.T, s *preparedSession, e *aliasTestEngine) uint32 {
	t.Helper()
	p, err := s.handle(22, []byte("SELECT ?"), e.call)
	if err != nil || len(p) == 0 || p[0][0] != 0 {
		t.Fatalf("prepare: %x %v", p, err)
	}
	return binary.LittleEndian.Uint32(p[0][1:])
}
func aliasExecute(id uint32, fresh bool) []byte {
	p := append(le32(id), 0, 1, 0, 0, 0, 0)
	if fresh {
		p = append(p, 1, 3, 0)
	} else {
		p = append(p, 0)
	}
	return append(p, 7, 0, 0, 0)
}
func aliasExpectError(t *testing.T, s *preparedSession, e *aliasTestEngine, payload []byte, errno uint16) {
	t.Helper()
	before := len(e.requests)
	p, err := s.handle(23, payload, e.call)
	if err != nil || len(p) != 1 || p[0][0] != 255 || binary.LittleEndian.Uint16(p[0][1:]) != errno || len(e.requests) != before {
		t.Fatalf("expected local %d: %x %v requests=%d/%d", errno, p, err, len(e.requests), before)
	}
}
func aliasExpectExecute(t *testing.T, s *preparedSession, e *aliasTestEngine, id, handle uint32, fresh bool) {
	t.Helper()
	before := len(e.requests)
	p, err := s.handle(23, aliasExecute(id, fresh), e.call)
	if err != nil || len(p) != 1 || p[0][0] != 0 || len(e.requests) != before+1 || e.requests[before].Handle != handle {
		t.Fatalf("execute %d ->%d: %x %v", id, handle, p, err)
	}
}
func TestLastStatementAliasLifecycle(t *testing.T) {
	const alias = ^uint32(0)
	s, e := aliasTestSession(t, 7)
	aliasExpectError(t, s, e, aliasExecute(alias, true), 1243)
	first := aliasPrepare(t, s, e)
	aliasExpectExecute(t, s, e, alias, 91, true)
	if len(s.types[first]) != 1 || s.types[alias] != nil {
		t.Fatal("alias type cache is not keyed by owned ID")
	}
	aliasExpectError(t, s, e, aliasExecute(alias, false), 1835)
	aliasExpectExecute(t, s, e, first, 91, false)
	second := aliasPrepare(t, s, e)
	aliasExpectExecute(t, s, e, first, 91, true)
	aliasExpectExecute(t, s, e, alias, 92, true)
	if _, err := s.handle(25, le32(first), e.call); err != nil {
		t.Fatal(err)
	}
	aliasExpectExecute(t, s, e, alias, 92, true)
	e.prepareFailure = "sql"
	p, err := s.handle(22, []byte("bad SQL"), e.call)
	if err != nil || binary.LittleEndian.Uint16(p[0][1:]) != 1064 {
		t.Fatal(p, err)
	}
	aliasExpectError(t, s, e, aliasExecute(alias, true), 1243)
	aliasExpectExecute(t, s, e, second, 92, false)
	aliasExpectError(t, s, e, aliasExecute(alias, true), 1243)
	e.prepareFailure = ""
	third := aliasPrepare(t, s, e)
	aliasExpectExecute(t, s, e, alias, 93, true)
	if _, err := s.handle(26, le32(alias), e.call); err != nil {
		t.Fatal(err)
	}
	aliasExpectExecute(t, s, e, alias, 93, true)
	if _, err := s.handle(25, le32(alias), e.call); err != nil {
		t.Fatal(err)
	}
	aliasExpectError(t, s, e, aliasExecute(third, true), 1243)
	aliasExpectError(t, s, e, aliasExecute(alias, true), 1243)
	aliasExpectExecute(t, s, e, second, 92, false)
	// Another physical session starts without an alias, even with matching wire IDs.
	other, otherEngine := aliasTestSession(t, 8)
	aliasExpectError(t, other, otherEngine, aliasExecute(alias, true), 1243)
	aliasPrepare(t, other, otherEngine)
	aliasExpectExecute(t, other, otherEngine, alias, 91, true)
	aliasExpectError(t, s, e, aliasExecute(alias, true), 1243)
}
func TestLastStatementAliasPrepareFailuresDoNotFallBack(t *testing.T) {
	for _, mode := range []string{"empty", "oversized", "sql", "transport", "metadata"} {
		t.Run(mode, func(t *testing.T) {
			s, e := aliasTestSession(t, 7)
			id := aliasPrepare(t, s, e)
			sql := []byte("SELECT ?")
			e.prepareFailure = mode
			if mode == "empty" {
				sql = nil
			}
			if mode == "oversized" {
				sql = bytes.Repeat([]byte{'x'}, preparedproto.MaxSQL+1)
			}
			_, err := s.handle(22, sql, e.call)
			if (mode == "transport" || mode == "metadata") && err == nil {
				t.Fatal("fatal prepare failure hidden")
			}
			if mode == "metadata" && e.requests[len(e.requests)-1].Operation != 25 {
				t.Fatal("metadata owner not unwound")
			}
			aliasExpectError(t, s, e, aliasExecute(^uint32(0), true), 1243)
			// Failed prepare does not discard the earlier explicitly owned statement.
			if _, ok := s.registry.Lookup(id); !ok {
				t.Fatal("earlier mapping removed")
			}
		})
	}
}
func TestLastStatementAliasLongDataAndResetShareOwnedState(t *testing.T) {
	const alias = ^uint32(0)
	s, e := aliasTestSession(t, 7)
	id := aliasPrepare(t, s, e)
	chunk := append(le32(alias), 0, 0, 'a')
	p, err := s.handle(24, chunk, e.call)
	if err != nil || len(p) != 0 || !s.long[id][0] || s.long[alias] != nil {
		t.Fatal("alias chunk mapping", p, err)
	}
	// LONG_DATA values are omitted inline, but direct execution still sends types.
	execute := append(le32(alias), 0, 1, 0, 0, 0, 0, 1, 252, 0)
	if _, err = s.handle(23, execute, e.call); err != nil || len(s.long) != 0 {
		t.Fatal("alias long execute", err)
	}
	values, err := preparedproto.DecodeValues(e.requests[len(e.requests)-1].Payload, 1)
	if err != nil || !values[0].Null {
		t.Fatal("long-data placeholder", values, err)
	}
	if _, err = s.handle(24, append(le32(alias), 9, 0, 'x'), e.call); err != nil {
		t.Fatal(err)
	}
	before := len(e.requests)
	p, err = s.handle(23, execute, e.call)
	if err != nil || len(e.requests) != before || binary.LittleEndian.Uint16(p[0][1:]) != 1210 {
		t.Fatal("alias deferred error", p, err)
	}
	if _, err = s.handle(26, le32(alias), e.call); err != nil || len(s.longErrors) != 0 || len(s.long) != 0 {
		t.Fatal("alias reset", err)
	}
	aliasExpectExecute(t, s, e, alias, 91, true)
	if _, err = s.handle(25, le32(alias), e.call); err != nil || len(s.types) != 0 {
		t.Fatal("alias close retained cache", err)
	}
	before = len(e.requests)
	p, err = s.handle(24, chunk, e.call)
	if err != nil || len(p) != 0 || len(e.requests) != before {
		t.Fatal("unknown alias LONG_DATA was not ignored", p, err)
	}
}
