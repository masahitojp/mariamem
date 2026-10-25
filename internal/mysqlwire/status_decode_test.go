package mysqlwire

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"testing"

	"github.com/masahitojp/mariamem/internal/guest"
)

func TestInternalStatusDecodedToTextPackets(t *testing.T) {
	var r guest.Result
	// Internal RETURNED_ROW plus IN_TRANS, AUTOCOMMIT and MORE_RESULTS.
	err := json.Unmarshal([]byte(`{"ok":true,"api_version":2,"results":[{"ok":true,"api_version":2,"server_status":65547,"affected":"0","insert_id":"0"},{"ok":true,"api_version":2,"server_status":65539,"affected":"0","insert_id":"0"}]}`), &r)
	if err != nil {
		t.Fatal(err)
	}
	p, err := packets(r)
	if err != nil || len(p) != 2 {
		t.Fatalf("packets=%d err=%v", len(p), err)
	}
	for i, want := range []uint16{11, 3} {
		if len(p[i]) != 7 || binary.LittleEndian.Uint16(p[i][3:5]) != want {
			t.Fatalf("packet %d: %x", i, p[i])
		}
	}
}

func TestInternalStatusDecodedPreparedChainMatchesNative(t *testing.T) {
	r, want := minimalPreparedChain(t)
	data, err := json.Marshal(r)
	if err != nil {
		t.Fatal(err)
	}
	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}
	raw["server_status"] = raw["server_status"].(float64) + 65536
	for _, part := range raw["results"].([]any) {
		p := part.(map[string]any)
		p["server_status"] = p["server_status"].(float64) + 65536
	}
	data, err = json.Marshal(raw)
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(data, &r); err != nil {
		t.Fatal(err)
	}
	got, err := preparedResultPackets(r)
	if err != nil || len(got) != len(want) {
		t.Fatalf("packets=%d err=%v", len(got), err)
	}
	for i := range want {
		if !bytes.Equal(got[i], want[i]) {
			t.Fatalf("packet %d: %x != %x", i, got[i], want[i])
		}
	}
}
