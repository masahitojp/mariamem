package guest

import (
	"bytes"
	"encoding/binary"
	"io"
	"testing"
)

func TestReadyTransportObservationsAreOptIn(t *testing.T) {
	for _, enabled := range []bool{false, true} {
		body := []byte(`{"request_id":0,"result":{"ready":true,"api_version":2,"max_sessions":16}}`)
		var frame bytes.Buffer
		if err := binary.Write(&frame, binary.LittleEndian, uint32(len(body))); err != nil {
			t.Fatal(err)
		}
		frame.Write(body)
		ready := make(chan response, 1)
		p := &Process{out: io.NopCloser(&frame), stopping: true, startupTiming: enabled, pending: map[uint32]chan response{0: ready}}
		p.read()
		response := <-ready
		if !response.result.Ready || response.err != nil {
			t.Fatal(response)
		}
		if enabled {
			if response.headerAt.IsZero() || response.decodedAt.Before(response.headerAt) {
				t.Fatal(response)
			}
		} else if !response.headerAt.IsZero() || !response.decodedAt.IsZero() {
			t.Fatal(response)
		}
	}
}
