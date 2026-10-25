package guest

import (
	"encoding/json"
	"fmt"
	"testing"
)

func TestResultInternalStatusProjectsProtocolBits(t *testing.T) {
	for _, tc := range []struct {
		raw  uint32
		want uint16
	}{
		{0, 0}, {2, 2}, {65538, 2}, {65539, 3},
		{65546, 10}, {65602, 66}, {65666, 130},
		{0xffffffff, 0xffff},
	} {
		t.Run(fmt.Sprint(tc.raw), func(t *testing.T) {
			var r Result
			data := fmt.Sprintf(`{"ok":true,"api_version":2,"warnings":7,"server_status":%d,"results":[{"ok":true,"server_status":%d}]}`, tc.raw, tc.raw)
			if err := json.Unmarshal([]byte(data), &r); err != nil {
				t.Fatal(err)
			}
			if !r.OK || r.Version != 2 || r.Warnings != 7 || r.Status != tc.want || len(r.Results) != 1 || r.Results[0].Status != tc.want || !r.Results[0].OK {
				t.Fatalf("lost reply fields or protocol status: %+v", r)
			}
		})
	}
}

func TestResultRejectsInvalidInternalStatus(t *testing.T) {
	for _, raw := range []string{`-1`, `4294967296`, `65538.5`, `65538.0`, `"65538"`, `null`, `true`, `{}`, `[]`} {
		for _, data := range []string{
			`{"server_status":` + raw + `}`,
			`{"server_status":2,"results":[{"server_status":` + raw + `}]}`,
		} {
			r := Result{Status: 3, OK: true}
			if err := json.Unmarshal([]byte(data), &r); err == nil {
				t.Fatalf("accepted %s", data)
			}
			if r.Status != 3 || !r.OK {
				t.Fatal("partially replaced result on decoding failure")
			}
		}
	}
}

func TestResultMissingStatusAllowsReadyEnvelope(t *testing.T) {
	var r Result
	if err := json.Unmarshal([]byte(`{"ready":true,"api_version":2,"max_sessions":16}`), &r); err != nil {
		t.Fatal(err)
	}
	if !r.Ready || r.Version != 2 || r.MaxSessions != 16 || r.Status != 0 {
		t.Fatalf("lost ready fields: %+v", r)
	}
}
