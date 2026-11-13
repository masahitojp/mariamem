package mysqlwire

import (
	"bytes"
	"encoding/json"
	"github.com/masahitojp/mariamem/internal/guest"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestPreparedRawRepresentationBoundary(t *testing.T) {
	for _, rows := range []string{`"raw_rows":["00002a000000"]`, `"raw_rows":[]`, `"rows":null,"raw_rows":[]`, `"rows":[],"raw_rows":[]`, `"raw_rows":null`, `"raw_rows":["00002a"]`, `"raw_rows":["00002a00000000"]`, `"raw_rows":["zz"]`, `"rows":[]`} {
		var r guest.Result
		err := json.Unmarshal([]byte(`{"ok":true,"binary_rows":true,"columns":[{"name":"v","catalog":"def","type":3}],`+rows+`}`), &r)
		if err == nil {
			_, err = preparedResultPackets(r)
		}
		valid := rows == `"raw_rows":["00002a000000"]` || rows == `"raw_rows":[]`
		if (err == nil) != valid {
			t.Fatalf("%s: %v", rows, err)
		}
	}
}
func TestHiddenRawOUTMalformedPayloadIsRejected(t *testing.T) {
	for _, payload := range []string{"00002a", "00002a00000000", "00032a000000"} {
		r, _ := nativeCapabilityPair(t, "OUT-only")
		r.Results[0].RawRows[0] = payload
		got, err := preparedClientPackets(r, false)
		if err == nil || got != nil {
			t.Fatal("hidden OUT emitted partial success", payload)
		}
	}
}

// Exercise the production C adapter and host parser together; the harness's
// engine API is mocked, so this is not generated-guest acceptance.
func TestCPreparedRawEnvelopeToHost(t *testing.T) {
	cc, err := exec.LookPath("clang")
	if err != nil {
		t.Skip("clang unavailable")
	}
	binary := filepath.Join(t.TempDir(), "prepared-owner")
	cmd := exec.Command(cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", "../../guest", "../../tests/fixtures/prepared_api_harness.c", "-o", binary)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("compile: %s %v", out, err)
	}
	for _, tc := range []struct {
		mode           string
		full, filtered int
	}{{"call-two", 17, 12}, {"call-later-error", 6, 6}} {
		t.Run(tc.mode, func(t *testing.T) {
			data, err := exec.Command(binary, tc.mode).Output()
			if err != nil {
				t.Fatal(err)
			}
			var r guest.Result
			if err := json.Unmarshal(data, &r); err != nil {
				t.Fatal(err)
			}
			if r.PreparedVersion != 2 || r.SessionGeneration != 1 {
				t.Fatal("private identity", r)
			}
			for _, c := range []struct {
				enabled bool
				count   int
			}{{true, tc.full}, {false, tc.filtered}} {
				packets, err := preparedClientPackets(r, c.enabled)
				if err != nil || len(packets) != c.count {
					t.Fatalf("enabled=%v count=%d err=%v", c.enabled, len(packets), err)
				}
				if !bytes.Equal(packets[3], []byte{0, 0, 42, 0, 0, 0}) {
					t.Fatalf("C row changed: %x", packets[3])
				}
			}
			// Corrupt a hidden OUT from the actual C envelope: no prefix may escape.
			if tc.mode == "call-two" {
				r.Results[2].RawRows[0] = "00002a"
				p, err := preparedClientPackets(r, false)
				if err == nil || p != nil {
					t.Fatal("hidden C OUT bypassed validation")
				}
			}
		})
	}
}
