package mysqlwire

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"testing"

	"github.com/masahitojp/mariamem/internal/guest"
)

func TestPreparedCapabilitiesFollowValidatedExecutionSupport(t *testing.T) {
	if preparedCapabilities(nil) != capabilities || preparedCapabilities(&preparedSession{}) != capabilities {
		t.Fatal("legacy/PREPARE-only guest advertised PS results")
	}
	if preparedCapabilities(&preparedSession{execute: true}) != capabilities|clientPSMultiResults {
		t.Fatal("prepared guest did not advertise PS results")
	}
	open := preparedOpen(7)
	if _, err := newPreparedSession(open, 2, open.PreparedOperations); err == nil {
		t.Fatal("mismatched Ready accepted")
	}
}

type nativeCallPart struct {
	Columns, Rows []string
	MetadataEnd   string `json:"metadata_end"`
	Terminal      string
	OKPacket      string `json:"ok_packet"`
	Status        uint16
}

func nativeCapabilityPair(t *testing.T, name string) (guest.Result, [][]byte) {
	t.Helper()
	data, err := os.ReadFile("../../tests/fixtures/prepared-p3-native.json")
	if err != nil {
		t.Fatal(err)
	}
	var ref struct {
		Cases map[string]struct{ Trace [][]nativeCallPart }
	}
	if err = json.Unmarshal(data, &ref); err != nil {
		t.Fatal(err)
	}
	parts := ref.Cases[name].Trace[0]
	r := guest.Result{OK: true, BinaryRows: true, Version: 2, StatementID: 91, Status: 2}
	var packets [][]byte
	decode := func(s string) []byte {
		b, e := hex.DecodeString(s)
		if e != nil {
			t.Fatal(e)
		}
		return b
	}
	for _, p := range parts {
		part := guest.Result{OK: true, BinaryRows: true, Version: 2, StatementID: 91, Status: p.Status, Affected: "0", InsertID: "0"}
		if p.OKPacket != "" {
			packets = append(packets, decode(p.OKPacket))
		} else {
			packets = append(packets, leint(uint64(len(p.Columns))))
			for _, col := range p.Columns {
				c := nativeTestColumn(t, col)
				if c.Type != 3 {
					t.Fatal("fixture numeric type changed")
				}
				part.Columns = append(part.Columns, c)
				packets = append(packets, decode(col))
			}
			packets = append(packets, decode(p.MetadataEnd))
			for _, row := range p.Rows {
				b := decode(row)
				if len(b) != 2+len(p.Columns)*4 {
					t.Fatal("fixture numeric width changed")
				}
				var cells []*guest.Cell
				for i := range p.Columns {
					cells = append(cells, &guest.Cell{Hex: hex.EncodeToString(b[2+i*4 : 6+i*4])})
				}
				part.Rows = append(part.Rows, cells)
				packets = append(packets, b)
			}
			packets = append(packets, decode(p.Terminal))
		}
		r.Results = append(r.Results, part)
	}
	return r, packets
}

func TestPreparedClientOUTNegotiationMatchesNativePairedConnections(t *testing.T) {
	for _, names := range [][2]string{{"OUT-only", "no-PS-flag-OUT"}, {"PS-flag-multiple", "no-PS-flag-multiple"}} {
		t.Run(names[0], func(t *testing.T) {
			internal, positive := nativeCapabilityPair(t, names[0])
			_, negative := nativeCapabilityPair(t, names[1])
			for _, mode := range []struct {
				enabled  bool
				expected [][]byte
			}{{true, positive}, {false, negative}} {
				got, err := preparedClientPackets(internal, mode.enabled)
				if err != nil {
					t.Fatal(err)
				}
				if len(got) != len(mode.expected) {
					t.Fatal(mode.enabled, len(got), len(mode.expected))
				}
				for i := range got {
					if hex.EncodeToString(got[i]) != hex.EncodeToString(mode.expected[i]) {
						t.Fatalf("PS=%v packet%d: %x != %x", mode.enabled, i, got[i], mode.expected[i])
					}
				}
			}
		})
	}
}

func TestUnexposedOUTStillRequiresFullValidation(t *testing.T) {
	for name, change := range map[string]func(*guest.Result){
		"corrupt-row":  func(r *guest.Result) { r.Results[0].Rows[0][0].Hex = "zz" },
		"wrong-handle": func(r *guest.Result) { r.Results[0].StatementID++ },
		"unfinished":   func(r *guest.Result) { r.Results[0].Status &^= 8 },
		"nested":       func(r *guest.Result) { r.Results[0].Results = []guest.Result{{}} },
	} {
		t.Run(name, func(t *testing.T) {
			r, _ := nativeCapabilityPair(t, "OUT-only")
			change(&r)
			got, err := preparedClientPackets(r, false)
			if err == nil || got != nil {
				t.Fatal("hidden OUT bypassed validation")
			}
		})
	}
	r, _ := minimalPreparedChain(t)
	r.Results = r.Results[:2]
	r.Results[1] = guest.Result{Version: 2, Errno: 1644, SQLState: "45000", Error: "later", Status: 2}
	got, err := preparedClientPackets(r, false)
	if err != nil || hex.EncodeToString(got[len(got)-1]) != hex.EncodeToString(ErrorPacket(1644, "45000", "later")) {
		t.Fatal("ordinary result/terminal SQL error hidden", err)
	}
}
