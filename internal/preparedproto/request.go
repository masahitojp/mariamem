// Package preparedproto defines the internal host/guest statement protocol.
// It is distinct from client MySQL packets and never contains native pointers.
package preparedproto

import (
	"encoding/binary"
	"errors"
)

const (
	Version          = 1
	GuestOpcode byte = 5
	Prepare     byte = 22
	Execute     byte = 23
	LongData    byte = 24
	Close       byte = 25
	Reset       byte = 26
	HeaderSize       = 16
	// The client SQL boundary remains 1 MiB; internal framing has separate overhead.
	MaxSQL      = 1 << 20
	MaxEnvelope = 32 << 20
)

var ErrEnvelope = errors.New("invalid prepared request envelope")

type Request struct {
	Operation  byte
	Generation uint32
	Handle     uint32
	Payload    []byte
}

// Encode validates operation-specific structure before allocating. Execute and
// LongData payloads are validated by their typed codecs, rather than as SQL.
func Encode(r Request) ([]byte, error) {
	if !valid(r) {
		return nil, ErrEnvelope
	}
	b := make([]byte, HeaderSize+len(r.Payload))
	b[0], b[1], b[2], b[3] = 'P', 'S', Version, r.Operation
	binary.LittleEndian.PutUint32(b[4:], r.Generation)
	binary.LittleEndian.PutUint32(b[8:], r.Handle)
	binary.LittleEndian.PutUint32(b[12:], uint32(len(r.Payload)))
	copy(b[HeaderSize:], r.Payload)
	return b, nil
}

// Decode borrows the packet; callers must retain it while using the payload.
func Decode(b []byte) (Request, error) {
	if len(b) < HeaderSize || len(b) > MaxEnvelope || b[0] != 'P' || b[1] != 'S' || b[2] != Version {
		return Request{}, ErrEnvelope
	}
	n := binary.LittleEndian.Uint32(b[12:])
	if uint64(n) != uint64(len(b)-HeaderSize) {
		return Request{}, ErrEnvelope
	}
	r := Request{b[3], binary.LittleEndian.Uint32(b[4:]), binary.LittleEndian.Uint32(b[8:]), b[HeaderSize:]}
	if !valid(r) {
		return Request{}, ErrEnvelope
	}
	return r, nil
}
func valid(r Request) bool {
	if r.Generation == 0 || len(r.Payload) > MaxEnvelope-HeaderSize {
		return false
	}
	switch r.Operation {
	case Prepare:
		return r.Handle == 0 && len(r.Payload) > 0 && len(r.Payload) <= MaxSQL
	case Close, Reset:
		return r.Handle != 0 && len(r.Payload) == 0
	case Execute, LongData:
		return r.Handle != 0
	default:
		return false
	}
}
