package mysqlwire

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"testing"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

func minimalPreparedChain(t *testing.T) (guest.Result, [][]byte) {
	t.Helper()
	data, err := os.ReadFile("../../tests/fixtures/prepared-call-native.json")
	if err != nil {
		t.Fatal(err)
	}
	var ref struct {
		Results []struct {
			Columns, Rows []string
			MetadataEnd   string `json:"metadata_end"`
			Terminal      string
			OKPacket      string `json:"ok_packet"`
			Status        uint16
		}
	}
	if err = json.Unmarshal(data, &ref); err != nil {
		t.Fatal(err)
	}
	result := guest.Result{OK: true, BinaryRows: true, Version: 2, StatementID: 91, Status: 2}
	var expected [][]byte
	decode := func(s string) []byte {
		b, e := hex.DecodeString(s)
		if e != nil {
			t.Fatal(e)
		}
		return b
	}
	for _, item := range ref.Results {
		part := guest.Result{OK: true, BinaryRows: true, Version: 2, StatementID: 91, Status: item.Status, Affected: "0", InsertID: "0"}
		if item.OKPacket != "" {
			expected = append(expected, decode(item.OKPacket))
		} else {
			expected = append(expected, leint(uint64(len(item.Columns))))
			for _, c := range item.Columns {
				part.Columns = append(part.Columns, nativeTestColumn(t, c))
				expected = append(expected, decode(c))
			}
			expected = append(expected, decode(item.MetadataEnd))
			for _, row := range item.Rows {
				b := decode(row)
				if len(b) != 2+4*len(part.Columns) {
					t.Fatal("unexpected numeric fixture shape")
				}
				cells := make([]*guest.Cell, len(part.Columns))
				for i := range cells {
					cells[i] = &guest.Cell{Hex: hex.EncodeToString(b[2+i*4 : 6+i*4])}
				}
				part.Rows = append(part.Rows, cells)
				expected = append(expected, b)
			}
			expected = append(expected, decode(item.Terminal))
		}
		result.Results = append(result.Results, part)
	}
	return result, expected
}

func TestPreparedChainMatchesNativePackets(t *testing.T) {
	r, expected := minimalPreparedChain(t)
	actual, err := preparedResultPackets(r)
	if err != nil {
		t.Fatal(err)
	}
	if len(actual) != len(expected) {
		t.Fatal(len(actual), len(expected))
	}
	for i := range actual {
		if hex.EncodeToString(actual[i]) != hex.EncodeToString(expected[i]) {
			t.Fatalf("packet %d: %x != %x", i, actual[i], expected[i])
		}
	}
	// Session identity is checked once on the outer reply; PREPARE must still
	// reject the same result shape, and EXECUTE must validate all nested parts.
	open := preparedOpen(7)
	open.PreparedOperations = []byte{22, 23, 25, 26}
	s, err := newPreparedSession(open, 1, open.PreparedOperations)
	if err != nil {
		t.Fatal(err)
	}
	r.PreparedVersion = 1
	r.SessionGeneration = 7
	if _, err = s.call(preparedproto.Execute, 91, nil, true, func([]byte, bool) (guest.Result, error) { return r, nil }); err != nil {
		t.Fatal(err)
	}
	if _, err = s.call(preparedproto.Prepare, 0, nil, true, func([]byte, bool) (guest.Result, error) { return r, nil }); err == nil {
		t.Fatal("PREPARE accepted result chain")
	}
}

func TestPreparedChainRejectsMalformedSuffixBeforeSending(t *testing.T) {
	for name, mutate := range map[string]func(*guest.Result){
		"empty":             func(r *guest.Result) { r.Results = []guest.Result{} },
		"text-top":          func(r *guest.Result) { r.BinaryRows = false },
		"unfinished-top":    func(r *guest.Result) { r.Status |= 8 },
		"wrong-handle":      func(r *guest.Result) { r.Results[1].StatementID++ },
		"missing-more":      func(r *guest.Result) { r.Results[1].Status &^= 8 },
		"last-more":         func(r *guest.Result) { r.Results[3].Status |= 8 },
		"text-part":         func(r *guest.Result) { r.Results[1].BinaryRows = false },
		"nested":            func(r *guest.Result) { r.Results[1].Results = []guest.Result{{OK: true}} },
		"bad-row":           func(r *guest.Result) { r.Results[2].Rows[0][0].Hex = "zz" },
		"bad-version":       func(r *guest.Result) { r.Results[1].Version = 1 },
		"nonterminal-error": func(r *guest.Result) { r.Results[1].OK = false },
		"missing-error":     func(r *guest.Result) { r.Results[3].OK = false },
	} {
		t.Run(name, func(t *testing.T) {
			r, _ := minimalPreparedChain(t)
			mutate(&r)
			packets, err := preparedResultPackets(r)
			if err == nil || packets != nil {
				t.Fatal("accepted or partially emitted malformed chain", err)
			}
		})
	}
}

func TestPreparedChainPreservesLaterSQLError(t *testing.T) {
	r, _ := minimalPreparedChain(t)
	r.Results = r.Results[:2]
	r.Results[1] = guest.Result{Version: 2, Errno: 1644, SQLState: "45000", Error: "after first result", Status: 2}
	packets, err := preparedResultPackets(r)
	if err != nil {
		t.Fatal(err)
	}
	want := ErrorPacket(1644, "45000", "after first result")
	if hex.EncodeToString(packets[len(packets)-1]) != hex.EncodeToString(want) {
		t.Fatal("lost later error")
	}
	if packets[4][3]&8 == 0 {
		t.Fatal("first result lost MORE_RESULTS")
	}
}
