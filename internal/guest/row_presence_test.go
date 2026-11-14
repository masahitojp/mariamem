package guest

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestResultRowPresenceAndDecodeAtomicity(t *testing.T) {
	for _, tc := range []struct {
		data            string
		rows, raw, fail bool
		cells, encoded  int
	}{
		{data: `{}`},
		{data: `{"rows":null}`, rows: true},
		{data: `{"rows":[]}`, rows: true},
		{data: `{"rows":[[{"$h":"00"}]]}`, rows: true, cells: 1},
		{data: `{"raw_rows":[]}`, raw: true},
		{data: `{"raw_rows":["0000"]}`, raw: true, encoded: 1},
		{data: `{"raw_rows":null}`, fail: true},
		{data: `{"raw_rows":{}}`, fail: true},
		{data: `{"raw_rows":[1]}`, fail: true},
		{data: `{"rows":null,"raw_rows":[]}`, rows: true, raw: true},
		{data: `{"raw_rows":null,"raw_rows":[]}`, raw: true},
		{data: `{"raw_rows":[],"raw_rows":null}`, fail: true},
		{data: `{"rows":[],"rows":null}`, rows: true},
	} {
		t.Run(tc.data, func(t *testing.T) {
			r := Result{OK: true, Status: 7}
			err := json.Unmarshal([]byte(tc.data), &r)
			if (err != nil) != tc.fail {
				t.Fatalf("error=%v", err)
			}
			if tc.fail {
				if !r.OK || r.Status != 7 {
					t.Fatal("partially published invalid result")
				}
				return
			}
			if r.RowsPresent != tc.rows || r.RawRowsPresent != tc.raw || len(r.Rows) != tc.cells || len(r.RawRows) != tc.encoded {
				t.Fatalf("presence/values: %+v", r)
			}
			if err = json.Unmarshal([]byte(`{}`), &r); err != nil || r.RowsPresent || r.RawRowsPresent || r.Rows != nil || r.RawRows != nil {
				t.Fatalf("reused result retained rows: %+v %v", r, err)
			}
		})
	}
	var r Result
	if err := json.Unmarshal([]byte(`{"results":[{"raw_rows":[]},{"rows":null}]}`), &r); err != nil || !r.Results[0].RawRowsPresent || !r.Results[1].RowsPresent {
		t.Fatalf("nested presence: %+v %v", r, err)
	}
	if err := json.Unmarshal([]byte(`{"results":[{"raw_rows":null}]}`), &r); err == nil {
		t.Fatal("accepted nested null raw_rows")
	}
}

func BenchmarkResultUnmarshalRaw64KiB(b *testing.B) {
	data := []byte(`{"ok":true,"api_version":2,"server_status":65538,"raw_rows":["0000` + strings.Repeat("78", 65536) + `"]}`)
	b.SetBytes(int64(len(data)))
	b.ReportAllocs()
	for b.Loop() {
		var r Result
		if err := json.Unmarshal(data, &r); err != nil {
			b.Fatal(err)
		}
	}
}
