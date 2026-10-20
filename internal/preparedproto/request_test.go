package preparedproto

import (
	"bytes"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"os"
	"testing"
)

func TestRequestIdentityAndBoundaries(t *testing.T) {
	for _, r := range []Request{{Prepare, 1, 0, []byte("SELECT ?")}, {Prepare, ^uint32(0), 0, bytes.Repeat([]byte{'a'}, MaxSQL)}, {Close, 2, ^uint32(0), nil}, {Reset, 3, 1, nil}, {Execute, 4, 2, []byte{0, 255}}, {LongData, 5, 3, []byte{0, 0, 0}}} {
		b, e := Encode(r)
		if e != nil {
			t.Fatal(e)
		}
		got, e := Decode(b)
		if e != nil || got.Operation != r.Operation || got.Generation != r.Generation || got.Handle != r.Handle || !bytes.Equal(got.Payload, r.Payload) {
			t.Fatalf("round trip: %+v %v", got, e)
		}
	}
	for _, r := range []Request{{Prepare, 0, 0, []byte("x")}, {Prepare, 1, 1, []byte("x")}, {Prepare, 1, 0, nil}, {Prepare, 1, 0, make([]byte, MaxSQL+1)}, {Close, 1, 0, nil}, {Reset, 1, 2, []byte{0}}, {27, 1, 0, nil}, {Execute, 1, 0, nil}, {LongData, 1, 0, nil}} {
		if _, e := Encode(r); e == nil {
			t.Fatalf("accepted invalid request: op=%d gen=%d handle=%d bytes=%d", r.Operation, r.Generation, r.Handle, len(r.Payload))
		}
	}
}
func TestMalformedEnvelopeRejected(t *testing.T) {
	good, _ := Encode(Request{Prepare, 3, 0, []byte("SELECT ?")})
	for n := 0; n < HeaderSize; n++ {
		if _, e := Decode(good[:n]); e == nil {
			t.Fatal("short header", n)
		}
	}
	for _, change := range []func([]byte){func(b []byte) { b[0] = 'X' }, func(b []byte) { b[2]++ }, func(b []byte) { b[3] = 27 }, func(b []byte) { binary.LittleEndian.PutUint32(b[4:], 0) }, func(b []byte) { binary.LittleEndian.PutUint32(b[8:], 1) }, func(b []byte) { binary.LittleEndian.PutUint32(b[12:], ^uint32(0)) }} {
		b := bytes.Clone(good)
		change(b)
		if _, e := Decode(b); e == nil {
			t.Fatal("accepted corrupt header")
		}
	}
	for _, b := range [][]byte{good[:len(good)-1], append(bytes.Clone(good), 0)} {
		if _, e := Decode(b); e == nil {
			t.Fatal("length mismatch")
		}
	}
}

func TestSharedGuestEnvelopeVector(t *testing.T) {
	data, err := os.ReadFile("../../tests/fixtures/prepared-envelope-v1.json")
	if err != nil {
		t.Fatal(err)
	}
	var v struct {
		Operation          byte
		Generation, Handle uint32
		SQL, Hex           string
	}
	if err = json.Unmarshal(data, &v); err != nil {
		t.Fatal(err)
	}
	want, err := hex.DecodeString(v.Hex)
	if err != nil {
		t.Fatal(err)
	}
	got, err := Encode(Request{v.Operation, v.Generation, v.Handle, []byte(v.SQL)})
	if err != nil || !bytes.Equal(got, want) {
		t.Fatalf("guest vector mismatch: %x %v", got, err)
	}
}
