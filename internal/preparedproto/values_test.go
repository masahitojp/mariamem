package preparedproto

import (
	"bytes"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"reflect"
	"testing"
)

func unhex(t *testing.T, s string) []byte {
	t.Helper()
	b, err := hex.DecodeString(s)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

// Each vector is a whole client EXECUTE body (id=1, no cursor, iteration=1,
// one parameter, new descriptors). Expectations are literal bytes, not numbers
// obtained through the encoder being tested.
func TestExecuteExactVectors(t *testing.T) {
	data, err := os.ReadFile("../../tests/fixtures/prepared-p2-values.json")
	if err != nil {
		t.Fatal(err)
	}
	var vectors []struct {
		Name, Packet, Value string
		Type                byte
		Unsigned, Null      bool
	}
	if err := json.Unmarshal(data, &vectors); err != nil {
		t.Fatal(err)
	}
	if len(vectors) != 19 {
		t.Fatal("missing vectors")
	}
	for _, tc := range vectors {
		t.Run(tc.Name, func(t *testing.T) {
			v, types, err := DecodeExecute(unhex(t, tc.Packet), 1, nil)
			if err != nil {
				t.Fatal(err)
			}
			want := Value{ParameterType{tc.Type, tc.Unsigned}, tc.Null, unhex(t, tc.Value)}
			if len(v) != 1 || v[0].ParameterType != want.ParameterType || v[0].Null != want.Null || !bytes.Equal(v[0].Bytes, want.Bytes) || types[0] != want.ParameterType {
				t.Fatalf("got %+v, want %+v", v, want)
			}
			internal, err := EncodeValues(v)
			if err != nil {
				t.Fatal(err)
			}
			back, err := DecodeValues(internal, 1)
			if err != nil || !reflect.DeepEqual(back, v) {
				t.Fatalf("internal: %+v %v", back, err)
			}
		})
	}
}

func TestInternalValueGoldenAndGuards(t *testing.T) {
	// Separate NULL/empty/binary values, with exact unsigned64 maximum.
	gold := unhex(t, "040000000602000000000000fe00000000000000fc000000030000004100420801000008000000ffffffffffffffff")
	values := []Value{{ParameterType{6, false}, true, nil}, {ParameterType{254, false}, false, nil}, {ParameterType{252, false}, false, []byte{'A', 0, 'B'}}, {ParameterType{8, true}, false, bytes.Repeat([]byte{255}, 8)}}
	got, err := EncodeValues(values)
	if err != nil || !bytes.Equal(got, gold) {
		t.Fatalf("golden %x %v", got, err)
	}
	decoded, err := DecodeValues(gold, 4)
	if err != nil || len(decoded) != 4 || !decoded[0].Null || decoded[1].Null || !bytes.Equal(decoded[3].Bytes, values[3].Bytes) {
		t.Fatalf("decode %+v %v", decoded, err)
	}
	for n := 0; n < len(gold); n++ {
		if _, err := DecodeValues(gold[:n], 4); err == nil {
			t.Fatalf("accepted prefix %d", n)
		}
	}
	for _, mutate := range []func([]byte){
		func(b []byte) { b[0] = 255 }, // wrong count
		func(b []byte) { b[4] = 17 },  // internal-only temporal type
		func(b []byte) { b[5] = 4 },   // unknown flags
		func(b []byte) { b[6] = 1 },   // reserved
		func(b []byte) { b[7] = 1 },
		func(b []byte) { binary.LittleEndian.PutUint32(b[8:], ^uint32(0)) },
		func(b []byte) { b[5] = 0 }, // MYSQL_TYPE_NULL must be null
	} {
		b := bytes.Clone(gold)
		mutate(b)
		if _, err := DecodeValues(b, 4); err == nil {
			t.Fatalf("accepted corrupt internal %x", b)
		}
	}
	if _, err := DecodeValues(append(bytes.Clone(gold), 0), 4); err == nil {
		t.Fatal("accepted suffix")
	}
	if _, err := DecodeValues(gold, 3); err == nil {
		t.Fatal("accepted native count mismatch")
	}
}

func TestExecuteTypeReuseIsTransactional(t *testing.T) {
	previous := []ParameterType{{8, true}, {254, false}}
	saved := append([]ParameterType(nil), previous...)
	// null bitmap=0, reuse=0, uint64 max, empty string.
	b := unhex(t, "0100000000010000000000ffffffffffffffff00")
	values, types, err := DecodeExecute(b, 2, previous)
	if err != nil || len(values) != 2 || !values[0].Unsigned || len(values[1].Bytes) != 0 {
		t.Fatalf("reuse %+v %v", values, err)
	}
	types[0].Type = 1
	if !reflect.DeepEqual(previous, saved) {
		t.Fatal("cache aliases caller")
	}
	for _, bad := range [][]byte{b[:len(b)-1], append(bytes.Clone(b), 0)} {
		if _, _, err := DecodeExecute(bad, 2, previous); err == nil {
			t.Fatal("accepted bad reuse")
		}
		if !reflect.DeepEqual(previous, saved) {
			t.Fatal("failed decode mutated cache")
		}
	}
	if _, _, err := DecodeExecute(b, 2, nil); err == nil {
		t.Fatal("reuse without descriptors")
	}
}

func TestExecuteMalformedAndUnsupported(t *testing.T) {
	good := unhex(t, "01000000000100000000010880ffffffffffffffff")
	for n := 0; n < len(good); n++ {
		if _, _, err := DecodeExecute(good[:n], 1, nil); err == nil {
			t.Fatalf("accepted prefix %d", n)
		}
	}
	for _, change := range []func([]byte){
		func(b []byte) { b[5] = 0 },   // iteration
		func(b []byte) { b[10] = 0 },  // missing reused descriptors
		func(b []byte) { b[10] = 2 },  // invalid new-types flag
		func(b []byte) { b[11] = 17 }, // server-internal type
		func(b []byte) { b[12] = 1 },  // unknown type flag
	} {
		b := bytes.Clone(good)
		change(b)
		if _, _, err := DecodeExecute(b, 1, nil); err == nil {
			t.Fatalf("accepted malformed %x", b)
		}
	}
	b := bytes.Clone(good)
	b[4] = 1
	if _, _, err := DecodeExecute(b, 1, nil); !errors.Is(err, ErrCursor) {
		t.Fatalf("cursor disposition %v", err)
	}
	if _, _, err := DecodeExecute(append(bytes.Clone(good), 0), 1, nil); err == nil {
		t.Fatal("suffix")
	}
	zero := unhex(t, "010000000001000000")
	if v, _, err := DecodeExecute(zero, 0, nil); err != nil || len(v) != 0 {
		t.Fatal("zero parameters", err)
	}
	if _, _, err := DecodeExecute(append(zero, 0), 0, nil); err == nil {
		t.Fatal("zero parameters suffix")
	}
}

func TestLengthEncodedBounds(t *testing.T) {
	for _, prefix := range []string{"fc", "fc00", "fd", "fd0000", "fe", "fe00000000000000", "feffffffffffffffff", "fb", "ff"} {
		b := unhex(t, "0100000000010000000001fc00"+prefix)
		if _, _, err := DecodeExecute(b, 1, nil); err == nil {
			t.Fatal("accepted length", prefix)
		}
	}
	for _, prefix := range []string{"00", "fc0000", "fd000000", "fe0000000000000000"} {
		b := unhex(t, "0100000000010000000001fc00"+prefix)
		if v, _, err := DecodeExecute(b, 1, nil); err != nil || len(v[0].Bytes) != 0 {
			t.Fatal("empty length", prefix, err)
		}
	}
}

func TestExecuteFreshTypesReplaceOnlyCandidateCache(t *testing.T) {
	previous := []ParameterType{{8, true}}
	packet := unhex(t, "0100000000010000000001fe0003410042")
	values, types, err := DecodeExecute(packet, 1, previous)
	if err != nil || types[0] != (ParameterType{254, false}) || !bytes.Equal(values[0].Bytes, []byte{'A', 0, 'B'}) {
		t.Fatalf("fresh types %+v %+v %v", types, values, err)
	}
	if previous[0] != (ParameterType{8, true}) {
		t.Fatal("fresh descriptors mutated committed cache")
	}
	if _, _, err := DecodeExecute(packet[:len(packet)-1], 1, previous); err == nil {
		t.Fatal("accepted truncated changed value")
	}
	if previous[0] != (ParameterType{8, true}) {
		t.Fatal("failed NEW types poisoned cache")
	}
}

func TestExecutePacketBudget(t *testing.T) {
	// 9-byte header, null byte, new-types byte, two descriptor bytes,
	// four-byte length prefix, then a blob reaching the existing bound.
	data := bytes.Repeat([]byte{0xff}, MaxSQL-17)
	packet := unhex(t, "0100000000010000000001fc00fd")
	packet = append(packet, byte(len(data)), byte(len(data)>>8), byte(len(data)>>16))
	packet = append(packet, data...)
	if len(packet) != MaxSQL {
		t.Fatal("test packet size")
	}
	values, _, err := DecodeExecute(packet, 1, nil)
	if err != nil || !bytes.Equal(values[0].Bytes, data) {
		t.Fatal("exact existing bound", err)
	}
	if _, _, err := DecodeExecute(append(packet, 0), 1, nil); err == nil {
		t.Fatal("packet bound+1")
	}
}

func TestTemporalShapesNotHostNormalization(t *testing.T) {
	for _, typ := range []byte{7, 10, 11, 12, 14} {
		for n := 0; n <= 13; n++ {
			valid := n == 0 || ((typ == 10 || typ == 14) && n == 4) || ((typ == 7 || typ == 12) && (n == 4 || n == 7 || n == 11)) || (typ == 11 && (n == 8 || n == 12))
			v := Value{ParameterType{typ, false}, false, bytes.Repeat([]byte{255}, n)}
			_, err := EncodeValues([]Value{v})
			if (err == nil) != valid {
				t.Fatalf("shape type=%d length=%d err=%v", typ, n, err)
			}
		}
	}
	// Calendar validity, sign/range and SQL mode are engine decisions, not a
	// reason for a codec to normalize or substitute the value before binding.
}

func TestValuesCapacityAndNullBitmapAcrossBytes(t *testing.T) {
	values := make([]Value, 65)
	for i := range values {
		values[i] = Value{ParameterType{252, false}, i%3 == 0, nil}
	}
	values[64].Bytes = bytes.Repeat([]byte{0, 255}, 4097)
	b, err := EncodeValues(values)
	if err != nil {
		t.Fatal(err)
	}
	got, err := DecodeValues(b, 65)
	if err != nil || len(got) != 65 || !bytes.Equal(got[64].Bytes, values[64].Bytes) {
		t.Fatal("capacity", err)
	}
	// 9 parameters: null bits0 and8, other TINY values in order.
	wire := unhex(t, "010000000001000000010101")
	for i := 0; i < 9; i++ {
		wire = append(wire, 1, 0)
	}
	wire = append(wire, 1, 2, 3, 4, 5, 6, 7)
	got, _, err = DecodeExecute(wire, 9, nil)
	if err != nil || !got[0].Null || !got[8].Null || got[7].Bytes[0] != 7 {
		t.Fatalf("bitmap %+v %v", got, err)
	}
	if _, err := EncodeValues(make([]Value, 65536)); err == nil {
		t.Fatal("count overflow")
	}
	large := Value{ParameterType{252, false}, false, make([]byte, MaxEnvelope-HeaderSize-12)}
	if b, err := EncodeValues([]Value{large}); err != nil || len(b) != MaxEnvelope-HeaderSize {
		t.Fatal("exact internal limit", err)
	}
	large.Bytes = append(large.Bytes, 0)
	if _, err := EncodeValues([]Value{large}); err == nil {
		t.Fatal("internal limit+1")
	}
}

func FuzzExecuteAndInternalValues(f *testing.F) {
	f.Add([]byte{1, 0, 0, 0, 0, 1, 0, 0, 0}, uint16(0))
	f.Add([]byte{1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 42}, uint16(1))
	f.Fuzz(func(t *testing.T, b []byte, n uint16) {
		if values, _, err := DecodeExecute(b, n, nil); err == nil {
			encoded, err := EncodeValues(values)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := DecodeValues(encoded, n); err != nil {
				t.Fatal(err)
			}
		}
		_, _ = DecodeValues(b, n)
	})
}

func TestBinaryRowsAgainstNativeCapture(t *testing.T) {
	data, err := os.ReadFile("../../tests/fixtures/prepared-p2-native.json")
	if err != nil {
		t.Fatal(err)
	}
	var native struct {
		Result string
		Cases  map[string]struct{ Rows []string }
	}
	if err := json.Unmarshal(data, &native); err != nil || native.Result != "PASS" {
		t.Fatal("invalid native capture", err)
	}
	data, err = os.ReadFile("../../tests/fixtures/prepared-p2-values.json")
	if err != nil {
		t.Fatal(err)
	}
	var vectors []struct {
		Name, Value    string
		Type           byte
		Unsigned, Null bool
	}
	if err := json.Unmarshal(data, &vectors); err != nil {
		t.Fatal(err)
	}
	for _, v := range vectors {
		cell := Value{ParameterType{v.Type, v.Unsigned}, v.Null, unhex(t, v.Value)}
		// The native engine canonicalizes FLOAT negative zero on evaluation.
		// The request decoder must retain its sign bit; a result encoder must
		// serialize the ENGINE'S result instead of echoing the input parameter.
		if v.Name == "float-negative-zero" {
			cell.Bytes = []byte{0, 0, 0, 0}
		}
		row, err := EncodeBinaryRow([]Value{cell}, 0xfffffe)
		want := native.Cases[v.Name].Rows
		if err != nil || len(want) != 1 || hex.EncodeToString(row) != want[0] {
			t.Fatalf("native row %s: %x %v want %v", v.Name, row, err, want)
		}
	}
	for name, values := range map[string][]Value{
		"large-binary": {{ParameterType{252, false}, false, bytes.Repeat([]byte{0, 255}, 4097)}},
		"rows1500":     {{ParameterType{1, false}, false, []byte{42}}},
	} {
		row, err := EncodeBinaryRow(values, 0xfffffe)
		if err != nil {
			t.Fatal(err)
		}
		for _, want := range native.Cases[name].Rows {
			if hex.EncodeToString(row) != want {
				t.Fatalf("native %s mismatch", name)
			}
		}
	}
	values := make([]Value, 65)
	for i := range values {
		values[i] = Value{ParameterType{1, false}, false, []byte{byte(i)}}
	}
	row, err := EncodeBinaryRow(values, 0xfffffe)
	if err != nil || hex.EncodeToString(row) != native.Cases["columns65"].Rows[0] {
		t.Fatal("native65 mismatch", err)
	}
}

func TestBinaryRowBitmapAndBudget(t *testing.T) {
	values := make([]Value, 9)
	for i := range values {
		values[i] = Value{ParameterType{1, false}, false, []byte{byte(i)}}
	}
	values[0].Null = true
	values[0].Bytes = nil
	values[6].Null = true
	values[6].Bytes = nil
	values[8].Null = true
	values[8].Bytes = nil
	// Result bitmap bits2,8,10, not parameter bitmap bits0,6,8.
	want := unhex(t, "000405010203040507")
	b, err := EncodeBinaryRow(values, len(want))
	if err != nil || !bytes.Equal(b, want) {
		t.Fatalf("bitmap %x %v", b, err)
	}
	if _, err := EncodeBinaryRow(values, len(want)-1); err == nil {
		t.Fatal("row over budget")
	}
	if _, err := EncodeBinaryRow(nil, 100); err == nil {
		t.Fatal("zero column row")
	}
	if _, err := EncodeBinaryRow(values, MaxEnvelope+1); err == nil {
		t.Fatal("excessive budget")
	}
	values[1].Bytes = nil
	if _, err := EncodeBinaryRow(values, 100); err == nil {
		t.Fatal("truncated numeric result")
	}
	for _, size := range []int{0, 250, 251, 65535, 65536} {
		value := Value{ParameterType{252, false}, false, bytes.Repeat([]byte{42}, size)}
		b, err := EncodeBinaryRow([]Value{value}, 100000)
		if err != nil {
			t.Fatal(err)
		}
		length, data, ok := readLength(b[2:])
		if !ok || length != uint64(size) || !bytes.Equal(data, value.Bytes) {
			t.Fatal("row length prefix", size)
		}
	}
}
