package mysqlwire

import (
	"bytes"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"testing"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

func TestExecuteSessionTypesOwnershipAndErrors(t *testing.T) {
	open := preparedOpen(7)
	open.PreparedOperations = []byte{22, 23, 25, 26}
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
	called := 0
	call := func(b []byte, monitor bool) (guest.Result, error) {
		called++
		r, err := preparedproto.Decode(b)
		if err != nil || r.Generation != 7 || r.Handle != 91 || r.Operation != 23 || !monitor {
			t.Fatalf("request %+v %v", r, err)
		}
		values, err := preparedproto.DecodeValues(r.Payload, 1)
		if err != nil || !values[0].Unsigned || !bytes.Equal(values[0].Bytes, bytes.Repeat([]byte{255}, 8)) {
			t.Fatalf("typed input %+v %v", values, err)
		}
		return guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: 7, StatementID: 91, BinaryRows: true, Status: 3, Affected: "18446744073709551615", InsertID: "9007199254740993"}, nil
	}
	packets, err := s.handle(23, payload, call)
	if err != nil || len(packets) != 1 || packets[0][0] != 0 || s.status != 3 {
		t.Fatalf("execute packets %x %v", packets, err)
	}
	wantOK, _ := hex.DecodeString("00fefffffffffffffffffe010000000000200003000000")
	if !bytes.Equal(packets[0], wantOK) {
		t.Fatalf("DML uint64 precision: %x", packets[0])
	}
	// Reuse only descriptors, not values or a second buffer of parameter bytes.
	reuse := append(bytes.Clone(payload[:10]), 0)
	reuse = append(reuse, payload[13:]...)
	if _, err := s.handle(23, reuse, call); err != nil || called != 2 {
		t.Fatal("reuse", err, called)
	}
	for _, bad := range [][]byte{payload[:3], payload[:len(payload)-1], append(bytes.Clone(payload), 0)} {
		reply, err := s.handle(23, bad, call)
		if err != nil || len(reply) != 1 || binary.LittleEndian.Uint16(reply[0][1:]) != 1835 {
			t.Fatal("malformed disposition", err)
		}
	}
	if called != 2 {
		t.Fatal("malformed input reached engine")
	}
	badOwner := bytes.Clone(payload)
	binary.LittleEndian.PutUint32(badOwner, id+1)
	reply, err := s.handle(23, badOwner, call)
	if err != nil || binary.LittleEndian.Uint16(reply[0][1:]) != 1243 || called != 2 {
		t.Fatal("ownership", err)
	}
	_, err = s.handle(23, payload, func([]byte, bool) (guest.Result, error) { return guest.Result{}, errors.New("transport") })
	if err == nil {
		t.Fatal("transport failure hidden")
	}
	// SQL failure keeps the descriptors consumed by the engine and returns its
	// original errno/state, preserving healthy following executions.
	reply, err = s.handle(23, payload, func([]byte, bool) (guest.Result, error) {
		return guest.Result{Version: 2, PreparedVersion: 1, SessionGeneration: 7, Errno: 1062, SQLState: "23000", Error: "duplicate", Status: 3}, nil
	})
	if err != nil || binary.LittleEndian.Uint16(reply[0][1:]) != 1062 {
		t.Fatal("SQL error", err)
	}
	if _, err = s.handle(23, reuse, call); err != nil {
		t.Fatal("following execute", err)
	}
}

func nativeTestColumn(t *testing.T, s string) guest.Column {
	t.Helper()
	b, err := hex.DecodeString(s)
	if err != nil {
		t.Fatal(err)
	}
	names := make([]string, 6)
	for i := range names {
		if len(b) == 0 || int(b[0]) > len(b)-1 || b[0] >= 251 {
			t.Fatal("native fixture name")
		}
		n := int(b[0])
		names[i] = string(b[1 : n+1])
		b = b[n+1:]
	}
	if len(b) != 13 || b[0] != 12 {
		t.Fatal("native fixture field")
	}
	return guest.Column{Catalog: names[0], DB: names[1], Table: names[2], OrgTable: names[3], Name: names[4], OrgName: names[5], Charset: binary.LittleEndian.Uint16(b[1:]), Length: binary.LittleEndian.Uint32(b[3:]), Type: b[7], Flags: binary.LittleEndian.Uint16(b[8:]), Decimals: b[10]}
}

func TestPreparedResultPacketsMatchNativeValues(t *testing.T) {
	data, err := os.ReadFile("../../tests/fixtures/prepared-p2-native.json")
	if err != nil {
		t.Fatal(err)
	}
	var native struct {
		Cases map[string]struct {
			Columns, Rows []string
			Terminal      string
		}
	}
	if err = json.Unmarshal(data, &native); err != nil {
		t.Fatal(err)
	}
	data, err = os.ReadFile("../../tests/fixtures/prepared-p2-values.json")
	if err != nil {
		t.Fatal(err)
	}
	var vectors []struct {
		Name, Value string
		Null        bool
	}
	if err = json.Unmarshal(data, &vectors); err != nil {
		t.Fatal(err)
	}
	for _, v := range vectors {
		ref := native.Cases[v.Name]
		r := guest.Result{OK: true, BinaryRows: true, Status: 2, Columns: []guest.Column{nativeTestColumn(t, ref.Columns[0])}, Rows: [][]*guest.Cell{{nil}}}
		if !v.Null {
			h := v.Value
			if v.Name == "float-negative-zero" {
				h = "00000000"
			} // actual engine result, not echoed input
			r.Rows[0][0] = &guest.Cell{Hex: h}
		}
		got, err := preparedResultPackets(r)
		if err != nil || len(got) != 5 || hex.EncodeToString(got[1]) != ref.Columns[0] || hex.EncodeToString(got[3]) != ref.Rows[0] || hex.EncodeToString(got[4]) != ref.Terminal {
			t.Fatalf("native %s: %x %v", v.Name, got, err)
		}
	}
}

func TestPreparedBinaryResultRejectsInvalidEnvelopes(t *testing.T) {
	good := guest.Result{OK: true, BinaryRows: true, Status: 2, Columns: []guest.Column{{Catalog: "def", Name: "v", Type: 3}}, Rows: [][]*guest.Cell{{{Hex: "2a000000"}}}}
	for _, change := range []func(*guest.Result){
		func(r *guest.Result) { r.OK = false },
		func(r *guest.Result) { r.BinaryRows = false },
		func(r *guest.Result) { r.Status |= 8 },
		func(r *guest.Result) { r.Results = []guest.Result{{}} },
		func(r *guest.Result) { r.Columns = []guest.Column{} },
		func(r *guest.Result) { r.Rows = [][]*guest.Cell{{}} },
		func(r *guest.Result) { r.Rows = [][]*guest.Cell{{{Hex: "zz"}}} },
		func(r *guest.Result) { r.Rows = [][]*guest.Cell{{{Hex: "2a"}}} },
		func(r *guest.Result) { r.Columns = nil },
	} {
		r := good
		change(&r)
		if _, err := preparedResultPackets(r); err == nil {
			t.Fatal("accepted invalid prepared binary response")
		}
	}
}
