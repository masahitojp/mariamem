package mysqlwire

import (
	"encoding/binary"
	"encoding/hex"
	"github.com/masahitojp/mariamem/internal/guest"
	"testing"
)

func TestSpikeMultiResultStatusAndError(t *testing.T) {
	ok := guest.Result{OK: true, Version: 2, Status: 2, Affected: "0", InsertID: "0"}
	first := ok
	first.Columns = []guest.Column{{Name: "n", Type: 3, Charset: 63}}
	first.Rows = [][]*guest.Cell{{{Hex: "31"}}}
	failure := guest.Result{Version: 2, Errno: 1064, SQLState: "42000", Error: "syntax"}
	for _, last := range []guest.Result{ok, failure} {
		p, err := packets(guest.Result{OK: true, Version: 2, Results: []guest.Result{first, last}})
		if err != nil || len(p) != 6 {
			t.Fatalf("packets=%d err=%v", len(p), err)
		}
		for _, i := range []int{2, 4} {
			if binary.LittleEndian.Uint16(p[i][3:])&8 == 0 {
				t.Fatal("missing MORE_RESULTS on intermediate EOF")
			}
		}
		if last.OK {
			if p[5][0] != 0 || binary.LittleEndian.Uint16(p[5][3:])&8 != 0 {
				t.Fatal("invalid terminal OK")
			}
		} else if p[5][0] != 255 || binary.LittleEndian.Uint16(p[5][1:]) != 1064 {
			t.Fatal("lost terminal error")
		}
	}
}

func TestSpikeMultiMalformedEnvelope(t *testing.T) {
	bad := guest.Result{Version: 2, Errno: 1064}
	ok := guest.Result{Version: 2, OK: true, Affected: "0", InsertID: "0"}
	for _, parts := range [][]guest.Result{{}, {bad, ok}, {{Version: 2, OK: true, Results: []guest.Result{ok}}}} {
		if _, err := packets(guest.Result{Version: 2, OK: true, Results: parts}); err == nil {
			t.Fatal("accepted malformed result chain")
		}
	}
}

func TestSpikeSetOptionValidationMatchesNativeUnknownOption(t *testing.T) {
	for _, payload := range [][]byte{{0, 0}, {1, 0}} {
		if setOptionError(payload) != nil {
			t.Fatal("valid option rejected")
		}
	}
	// Captured unchanged from the pinned native MariaDB 12.3.3 COM_SET_OPTION.
	expected, _ := hex.DecodeString("ff1704233038533031556e6b6e6f776e20636f6d6d616e64")
	got := setOptionError([]byte{255, 255})
	if string(got) != string(expected) {
		t.Fatalf("unknown option packet %x", got)
	}
	for _, payload := range [][]byte{nil, {0}, {0, 0, 0}} {
		if setOptionError(payload) == nil {
			t.Fatal("invalid option size accepted")
		}
	}
}
