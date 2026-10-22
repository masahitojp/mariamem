package mysqlwire

import (
	"bytes"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"os"
	"testing"
)

func TestPreparedWireFlagsPreserveOtherBitsAndNonNumericTypes(t *testing.T) {
	// Explicit public C API type IDs from the pinned header, independent of the
	// predicate used by production. Timestamp and BIT deliberately stay outside.
	numeric := map[uint8]bool{0: true, 1: true, 2: true, 3: true, 4: true, 5: true, 6: true, 8: true, 9: true, 13: true, 246: true}
	for typ := 0; typ < 256; typ++ {
		want := uint16(0xffff)
		if numeric[uint8(typ)] {
			want = 0x7fff
		}
		if got := preparedWireFlags(uint8(typ), 0xffff); got != want {
			t.Fatalf("type %d: %04x want %04x", typ, got, want)
		}
		for _, flags := range []uint16{0, 1, 32, 128, 256, 512, 0x7fff} {
			if got := preparedWireFlags(uint8(typ), flags); got != flags {
				t.Fatalf("type %d changed native low flags %04x", typ, flags)
			}
		}
	}
}

type capturedPrepareMetadata struct {
	Metadata map[string]struct {
		Parameters []string `json:"parameters"`
		Columns    []string `json:"columns"`
		Warnings   uint16   `json:"warnings"`
	} `json:"metadata"`
}

func readPrepareMetadata(t *testing.T, path string) capturedPrepareMetadata {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var record capturedPrepareMetadata
	if err = json.Unmarshal(data, &record); err != nil {
		t.Fatal(err)
	}
	return record
}

// The captured 12.3.3 packets use one-byte lengths for all six metadata strings.
// Reject another layout explicitly; don't guess which bytes are flags.
func capturedFieldOffset(t *testing.T, packet []byte) int {
	t.Helper()
	offset := 0
	for i := 0; i < 6; i++ {
		if offset >= len(packet) || packet[offset] >= 251 {
			t.Fatal("unexpected captured string length")
		}
		offset += 1 + int(packet[offset])
	}
	if offset >= len(packet) || packet[offset] != 12 || len(packet)-offset != 13 {
		t.Fatal("unexpected captured fixed metadata")
	}
	return offset + 1
}

func TestCapturedPreparedMetadataMatchesNativeExactlyAfterWireConversion(t *testing.T) {
	native := readPrepareMetadata(t, "../../tests/fixtures/prepared-p1-native.json")
	embedded := readPrepareMetadata(t, "../../tests/fixtures/prepared-p1-embedded-metadata.json")
	if len(native.Metadata) != 6 || len(embedded.Metadata) != len(native.Metadata) {
		t.Fatal("missing captured cases")
	}
	changed, checked := 0, 0
	for name, want := range native.Metadata {
		got, ok := embedded.Metadata[name]
		if !ok || got.Warnings != want.Warnings {
			t.Fatal("case/warnings mismatch", name)
		}
		for group, expected := range [][]string{want.Parameters, want.Columns} {
			actual := got.Parameters
			if group == 1 {
				actual = got.Columns
			}
			if len(actual) != len(expected) {
				t.Fatal("descriptor count changed", name)
			}
			for i, encoded := range actual {
				packet, err := hex.DecodeString(encoded)
				if err != nil {
					t.Fatal(err)
				}
				golden, err := hex.DecodeString(expected[i])
				if err != nil {
					t.Fatal(err)
				}
				fixed := capturedFieldOffset(t, packet)
				before := binary.LittleEndian.Uint16(packet[fixed+7:])
				after := preparedWireFlags(packet[fixed+6], before)
				if before != after {
					changed++
				}
				binary.LittleEndian.PutUint16(packet[fixed+7:], after)
				if !bytes.Equal(packet, golden) {
					t.Fatalf("%s group %d column %d differs from unchanged native packet", name, group, i)
				}
				checked++
			}
		}
	}
	if changed != 68 || checked != 140 {
		t.Fatalf("unexpected capture coverage: %d fixes in %d descriptors", changed, checked)
	}
}
