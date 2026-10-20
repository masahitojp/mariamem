package mysqlwire

import (
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"testing"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

func TestPreparedParameterDescriptorsMatchExpandedNativeControl(t *testing.T) {
	data, err := os.ReadFile("../../tests/fixtures/prepared-p1-native.json")
	if err != nil {
		t.Fatal(err)
	}
	var native struct {
		Metadata map[string]struct {
			Parameters []string `json:"parameters"`
		} `json:"metadata"`
	}
	if err = json.Unmarshal(data, &native); err != nil {
		t.Fatal(err)
	}
	column, err := preparedColumn(preparedParameter())
	if err != nil {
		t.Fatal(err)
	}
	checked := 0
	for name, row := range native.Metadata {
		for _, expected := range row.Parameters {
			checked++
			if hex.EncodeToString(column) != expected {
				t.Fatal("native parameter descriptor mismatch", name)
			}
		}
	}
	if checked != 71 {
		t.Fatal("expanded metadata cases missing", checked)
	}
}

func preparedOpen(generation uint32) guest.Result {
	return guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: generation, Status: 2, PreparedOperations: []byte{22, 25, 26}}
}
func TestPreparedOpenDoesNotSilentlyDowngrade(t *testing.T) {
	for _, ready := range []struct {
		version    int
		operations []uint8
	}{{0, nil}, {2, []uint8{22, 25, 26}}, {1, []uint8{22, 25}}} {
		if _, err := newPreparedSession(preparedOpen(7), ready.version, ready.operations); err == nil {
			t.Fatal("Ready/open mismatch accepted", ready)
		}
	}
	if s, err := newPreparedSession(guest.Result{OK: true, Version: 2}, 0, nil); err != nil || s != nil {
		t.Fatal(s, err)
	}
	for _, change := range []func(*guest.Result){func(r *guest.Result) { r.PreparedVersion = 2 }, func(r *guest.Result) { r.SessionGeneration = 0 }, func(r *guest.Result) { r.PreparedOperations = []byte{22, 25} }, func(r *guest.Result) { r.PreparedOperations = []byte{22, 25, 26, 25} }, func(r *guest.Result) { r.PreparedVersion = 0 }} {
		r := preparedOpen(7)
		change(&r)
		if _, err := newPreparedSession(r, 1, []uint8{22, 25, 26}); err == nil {
			t.Fatal("invalid open accepted", r)
		}
	}
}
func TestPreparedSessionOwnershipNoResponseAndUnwind(t *testing.T) {
	s, err := newPreparedSession(preparedOpen(7), 1, []uint8{22, 25, 26})
	if err != nil {
		t.Fatal(err)
	}
	var calls []preparedproto.Request
	var monitors []bool
	corrupt, transportError := false, false
	call := func(b []byte, monitor bool) (guest.Result, error) {
		r, err := preparedproto.Decode(b)
		if err != nil {
			t.Fatal(err)
		}
		calls = append(calls, r)
		monitors = append(monitors, monitor)
		if transportError {
			return guest.Result{}, errors.New("injected transport failure")
		}
		result := guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: 7, Status: 2}
		if r.Operation == 22 {
			result.StatementID = uint32(len(calls))
			result.ParamCount = 1
			if corrupt {
				result.Rows = [][]*guest.Cell{{}}
			}
		}
		return result, nil
	}
	p, err := s.handle(22, []byte("SELECT ?"), call)
	if err != nil {
		t.Fatal(err)
	}
	id := binary.LittleEndian.Uint32(p[0][1:])
	if id != 1 {
		t.Fatal(id)
	}
	if entry, ok := s.registry.Lookup(id); !ok || entry.Handle != 1 {
		t.Fatal(entry, ok)
	}
	if _, err = s.handle(26, le32(id), call); err != nil {
		t.Fatal(err)
	}
	p, err = s.handle(25, le32(id), call)
	if err != nil || p == nil || len(p) != 0 {
		t.Fatal(p, err)
	}
	if monitors[len(monitors)-1] {
		t.Fatal("CLOSE consumed next client packet through monitor")
	}
	if _, ok := s.registry.Lookup(id); ok {
		t.Fatal("closed statement retained")
	}
	count := len(calls)
	p, err = s.handle(25, le32(id), call)
	if err != nil || len(p) != 0 || len(calls) != count {
		t.Fatal("unknown CLOSE not ignored", p, err)
	}
	p, err = s.handle(26, le32(id), call)
	if err != nil || binary.LittleEndian.Uint16(p[0][1:]) != 1243 || len(calls) != count {
		t.Fatal("closed RESET not rejected", p, err)
	}
	corrupt = true
	if _, err = s.handle(22, []byte("SELECT ?"), call); err == nil {
		t.Fatal("malformed metadata accepted")
	}
	if calls[len(calls)-1].Operation != 25 || monitors[len(monitors)-1] {
		t.Fatal("failed metadata did not unwind native owner")
	}
	corrupt = false
	transportError = true
	if _, err = s.handle(22, []byte("SELECT ?"), call); err == nil {
		t.Fatal("transport failure hidden")
	}
}
func TestPreparedSessionIDsBelongToFinalPhysicalGeneration(t *testing.T) {
	a, _ := newPreparedSession(preparedOpen(1), 1, []uint8{22, 25, 26})
	b, _ := newPreparedSession(preparedOpen(2), 1, []uint8{22, 25, 26})
	aID, _ := a.registry.Add(1, 51, 1)
	bID, _ := b.registry.Add(2, 71, 1)
	if aID != bID {
		t.Fatal("fixture needs equal wire IDs")
	}
	for _, tc := range []struct {
		s                  *preparedSession
		handle, generation uint32
	}{{a, 51, 1}, {b, 71, 2}} {
		_, err := tc.s.handle(26, le32(aID), func(data []byte, monitor bool) (guest.Result, error) {
			r, e := preparedproto.Decode(data)
			if e != nil || r.Generation != tc.generation || r.Handle != tc.handle || !monitor {
				t.Fatal(r, e)
			}
			return guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: tc.generation, Status: 2}, nil
		})
		if err != nil {
			t.Fatal(err)
		}
	}
}
