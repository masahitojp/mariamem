package preparedproto

import (
	"encoding/binary"
	"reflect"
	"testing"
)

func TestLongDataOmissionWinsOverNullBitmapAndRetainsOtherValues(t *testing.T) {
	// param0 streamed BLOB, param1 inline LONG, param2 streamed string (bitmap NULL)
	p := binary.LittleEndian.AppendUint32(nil, 7)
	p = append(p, 0, 1, 0, 0, 0, 4, 1, 252, 0, 3, 0, 253, 0)
	p = binary.LittleEndian.AppendUint32(p, 123)
	pending := map[uint16]bool{0: true, 2: true}
	values, types, err := DecodeExecuteLongData(p, 3, nil, pending)
	if err != nil {
		t.Fatal(err)
	}
	if !values[0].Null || !values[2].Null || values[1].Null || binary.LittleEndian.Uint32(values[1].Bytes) != 123 {
		t.Fatal(values)
	}
	if !reflect.DeepEqual(types, []ParameterType{{Type: 252}, {Type: 3}, {Type: 253}}) {
		t.Fatal(types)
	}
	b, err := EncodeValues(values)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = DecodeValues(b, 3); err != nil {
		t.Fatal(err)
	}
	// Unexpected inline bytes are not silently swallowed for streamed parameters.
	if _, _, err = DecodeExecuteLongData(append(p, 1), 3, nil, pending); err == nil {
		t.Fatal("trailing bytes accepted")
	}
	if _, _, err = DecodeExecute(p, 3, nil); err == nil {
		t.Fatal("ordinary decoder accepted omitted data")
	}
}
func TestLongDataReuseStillChecksTypeWidthAndTruncation(t *testing.T) {
	p := []byte{1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0} // one NULL-bit=0 parameter, reused type, no inline value
	previous := []ParameterType{{Type: 252}}
	v, types, err := DecodeExecuteLongData(p, 1, previous, map[uint16]bool{0: true})
	if err != nil || !v[0].Null {
		t.Fatal(v, err)
	}
	types[0].Type = 3
	if previous[0].Type != 252 {
		t.Fatal("candidate aliases cache")
	}
	for n := 0; n < len(p); n++ {
		if _, _, err := DecodeExecuteLongData(p[:n], 1, previous, map[uint16]bool{0: true}); err == nil {
			t.Fatal("truncation accepted", n)
		}
	}
	if _, _, err := DecodeExecuteLongData(p, 1, nil, map[uint16]bool{0: true}); err == nil {
		t.Fatal("missing descriptor cache accepted")
	}
	p[10] = 1
	p = append(p, 200, 0)
	if _, _, err := DecodeExecuteLongData(p, 1, previous, map[uint16]bool{0: true}); err == nil {
		t.Fatal("unknown type accepted")
	}
}
