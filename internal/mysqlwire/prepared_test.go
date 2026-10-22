package mysqlwire

import (
	"bytes"
	"encoding/binary"
	"github.com/masahitojp/mariamem/internal/guest"
	"testing"
)

func preparedResult() guest.Result {
	return guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: 7, StatementID: 99, ParamCount: 65, Parameters: make([]guest.Column, 65), Status: 2, Columns: make([]guest.Column, 65)}
}
func TestPrepareMetadataBeyondPrototypeCounts(t *testing.T) {
	r := preparedResult()
	for i := range r.Columns {
		r.Columns[i] = guest.Column{Name: "value", Type: 3, Charset: 63, Flags: 32, Length: 11}
	}
	p, e := preparePackets(r, 7, 3)
	if e != nil {
		t.Fatal(e)
	}
	if len(p) != 133 || binary.LittleEndian.Uint32(p[0][1:]) != 3 || binary.LittleEndian.Uint16(p[0][5:]) != 65 || binary.LittleEndian.Uint16(p[0][7:]) != 65 {
		t.Fatal("metadata counts/identity lost", len(p))
	}
	for _, i := range []int{66, 132} {
		if p[i][0] != 254 {
			t.Fatal("missing EOF", i)
		}
	}
	r.ParamCount = 0
	r.Parameters = nil
	r.Columns = nil
	p, e = preparePackets(r, 7, 4)
	if e != nil || len(p) != 1 {
		t.Fatal("zero metadata", p, e)
	}
}
func TestPrepareRejectsWrongIdentityAndCorruptMetadata(t *testing.T) {
	for _, change := range []func(*guest.Result){func(r *guest.Result) { r.Version = 1 }, func(r *guest.Result) { r.PreparedVersion = 2 }, func(r *guest.Result) { r.SessionGeneration++ }, func(r *guest.Result) { r.StatementID = 0 }, func(r *guest.Result) { r.ParamCount = 65536 }, func(r *guest.Result) { r.Columns = make([]guest.Column, 65536) }, func(r *guest.Result) { r.Results = []guest.Result{{}} }, func(r *guest.Result) { r.OK = false; r.Errno = 0 }} {
		r := preparedResult()
		change(&r)
		if _, e := preparePackets(r, 7, 3); e == nil {
			t.Fatal("invalid response accepted")
		}
	}
	r := preparedResult()
	if _, e := preparePackets(r, 7, 0); e == nil {
		t.Fatal("zero public handle")
	}
}
func TestPrepareKeepsNativeErrorPacket(t *testing.T) {
	r := preparedResult()
	r.OK = false
	r.Errno = 1064
	r.SQLState = "42000"
	r.Error = "syntax error"
	p, e := preparePackets(r, 7, 0)
	if e != nil || len(p) != 1 || !bytes.Equal(p[0], ErrorPacket(1064, "42000", "syntax error")) {
		t.Fatal(p, e)
	}
}

// A generic descriptor is only a test input. Production must forward each
// engine-owned descriptor and reject missing metadata instead of inventing it.
func preparedParameter() guest.Column {
	return guest.Column{Catalog: "def", Name: "?", Type: 6, Charset: 63, Flags: 128}
}
func TestPrepareForwardsParameterNamesAndRejectsMissingDescriptors(t *testing.T) {
	r := preparedResult()
	r.ParamCount = 2
	first := preparedParameter()
	first.Name = "engine alias"
	second := preparedParameter()
	second.Name = "日本語"
	second.Flags = 0x100
	r.Parameters = []guest.Column{first, second}
	r.Columns = nil
	packets, err := preparePackets(r, 7, 3)
	if err != nil {
		t.Fatal(err)
	}
	for i, field := range r.Parameters {
		want, _ := preparedColumn(field)
		if !bytes.Equal(packets[i+1], want) {
			t.Fatal("parameter metadata lost", i)
		}
	}
	for _, bad := range [][]guest.Column{nil, {first}, {first, second, first}} {
		r.Parameters = bad
		if _, err := preparePackets(r, 7, 3); err == nil {
			t.Fatal("missing/excess metadata accepted")
		}
	}
}
