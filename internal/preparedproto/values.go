package preparedproto

import (
	"encoding/binary"
	"errors"
)

var (
	ErrValue   = errors.New("invalid prepared typed value")
	ErrExecute = errors.New("invalid prepared execute packet")
	ErrCursor  = errors.New("prepared server-side cursors are not supported")
)

// ParameterType is the client descriptor, including its unsigned bit. Keeping
// this separate from values permits type reuse without caching parameter data.
type ParameterType struct {
	Type     byte
	Unsigned bool
}

// Value carries exact little-endian numeric bytes, raw string/decimal bytes, or
// the binary temporal body WITHOUT its length prefix. It contains no Go time or
// floating-point conversion. Null and an empty, non-null value are distinct.
type Value struct {
	ParameterType
	Null  bool
	Bytes []byte
}

// valueShape follows the pinned MariaDB sql_prepare.cc parameter type set.
// Fixed widths are positive; -1 means length-encoded bytes, -2 temporal bodies.
// Internal-only TIMESTAMP2/DATETIME2/TIME2 and unknown codes are rejected.
func valueShape(t byte) int {
	switch t {
	case 1:
		return 1 // TINY
	case 2, 13:
		return 2 // SHORT, YEAR
	case 3, 9, 4:
		return 4 // LONG, INT24, FLOAT
	case 8, 5:
		return 8 // LONGLONG, DOUBLE
	case 6:
		return 0 // NULL
	case 7, 10, 11, 12, 14:
		return -2 // TIMESTAMP, DATE, TIME, DATETIME, NEWDATE
	case 0, 15, 16, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255:
		return -1 // DECIMAL, VARCHAR, BIT, NEWDECIMAL, ENUM/SET, blobs/strings, GEOMETRY
	default:
		return -3
	}
}

func validValue(v Value) bool {
	s := valueShape(v.Type)
	if s == -3 {
		return false
	}
	if v.Null {
		return len(v.Bytes) == 0
	}
	if s >= 0 {
		return s != 0 && len(v.Bytes) == s
	}
	if s == -1 {
		return true
	}
	n := len(v.Bytes)
	switch v.Type {
	case 10, 14:
		return n == 0 || n == 4
	case 7, 12:
		return n == 0 || n == 4 || n == 7 || n == 11
	case 11:
		return n == 0 || n == 8 || n == 12
	}
	return false
}

// EncodeValues builds the internal EXECUTE payload: u32 count, followed by
// {u8 type,u8 flags(bit0 unsigned,bit1 null),u16 reserved=0,u32 length,bytes}.
// Full validation and size accounting precede allocation. The guest must check
// this independently against mysql_stmt_param_count before binding anything.
func EncodeValues(values []Value) ([]byte, error) {
	if len(values) > 65535 {
		return nil, ErrValue
	}
	n := 4
	for _, v := range values {
		if !validValue(v) || len(v.Bytes) > MaxEnvelope-HeaderSize-n-8 {
			return nil, ErrValue
		}
		n += 8 + len(v.Bytes)
	}
	b := make([]byte, 4, n)
	binary.LittleEndian.PutUint32(b, uint32(len(values)))
	for _, v := range values {
		flags := byte(0)
		if v.Unsigned {
			flags |= 1
		}
		if v.Null {
			flags |= 2
		}
		b = append(b, v.Type, flags, 0, 0)
		b = binary.LittleEndian.AppendUint32(b, uint32(len(v.Bytes)))
		b = append(b, v.Bytes...)
	}
	return b, nil
}

// DecodeValues borrows b. Count and all lengths are validated before creating
// the value slice; a declared count cannot cause an allocation disproportionate
// to the input. No native-width arithmetic or pointer is part of this format.
func DecodeValues(b []byte, expected uint16) ([]Value, error) {
	if len(b) < 4 || len(b) > MaxEnvelope-HeaderSize || binary.LittleEndian.Uint32(b) != uint32(expected) {
		return nil, ErrValue
	}
	scan := func(dst []Value) error {
		p := b[4:]
		for i := 0; i < int(expected); i++ {
			if len(p) < 8 || p[1]&^3 != 0 || p[2] != 0 || p[3] != 0 {
				return ErrValue
			}
			n := uint64(binary.LittleEndian.Uint32(p[4:]))
			if n > uint64(len(p)-8) {
				return ErrValue
			}
			v := Value{ParameterType{p[0], p[1]&1 != 0}, p[1]&2 != 0, p[8 : 8+int(n)]}
			if !validValue(v) {
				return ErrValue
			}
			if v.Null {
				v.Bytes = nil
			}
			if dst != nil {
				dst[i] = v
			}
			p = p[8+int(n):]
		}
		if len(p) != 0 {
			return ErrValue
		}
		return nil
	}
	if err := scan(nil); err != nil {
		return nil, err
	}
	values := make([]Value, int(expected))
	_ = scan(values)
	return values, nil
}

// DecodeExecute decodes a COM_STMT_EXECUTE body INCLUDING its statement id,
// excluding the command byte. Ownership resolution remains with the caller.
// The returned descriptors are a private candidate cache: malformed packets
// never alter previous. Values borrow packet; previous and result never alias.
func DecodeExecute(packet []byte, count uint16, previous []ParameterType) ([]Value, []ParameterType, error) {
	return DecodeExecuteLongData(packet, count, previous, nil)
}

// DecodeExecuteLongData omits inline values for parameters held by the engine.
// A typed NULL is an internal placeholder, not replacement stream data: the
// embedded engine's existing long value takes precedence over this binding.
// No chunk bytes are buffered here; even an empty stream overrides the bitmap.
func DecodeExecuteLongData(packet []byte, count uint16, previous []ParameterType, pending map[uint16]bool) ([]Value, []ParameterType, error) {
	if len(packet) < 9 || len(packet) > MaxSQL {
		return nil, nil, ErrExecute
	}
	if packet[4] != 0 {
		return nil, nil, ErrCursor
	}
	if binary.LittleEndian.Uint32(packet[5:]) != 1 {
		return nil, nil, ErrExecute
	}
	p := packet[9:]
	if count == 0 {
		if len(p) != 0 {
			return nil, nil, ErrExecute
		}
		return []Value{}, []ParameterType{}, nil
	}
	n := int(count)
	maskSize := (n + 7) / 8
	if len(p) < maskSize+1 {
		return nil, nil, ErrExecute
	}
	mask, fresh := p[:maskSize], p[maskSize] != 0
	if p[maskSize] > 1 {
		return nil, nil, ErrExecute
	}
	p = p[maskSize+1:]
	var types []ParameterType
	if fresh {
		if len(p) < 2*n {
			return nil, nil, ErrExecute
		}
		types = make([]ParameterType, n)
		for i := range types {
			if p[2*i+1]&^0x80 != 0 || valueShape(p[2*i]) == -3 {
				return nil, nil, ErrExecute
			}
			types[i] = ParameterType{p[2*i], p[2*i+1]&0x80 != 0}
		}
		p = p[2*n:]
	} else {
		if len(previous) != n {
			return nil, nil, ErrExecute
		}
		types = append([]ParameterType(nil), previous...)
	}
	values := make([]Value, n)
	for i, t := range types {
		if valueShape(t.Type) == -3 {
			return nil, nil, ErrExecute
		}
		v := Value{ParameterType: t, Null: mask[i/8]&(1<<uint(i%8)) != 0 || t.Type == 6}
		if pending[uint16(i)] {
			v.Null = true
			values[i] = v
			continue
		}
		if !v.Null {
			size := valueShape(t.Type)
			var length uint64
			if size > 0 {
				length = uint64(size)
			} else if size == -2 {
				if len(p) == 0 {
					return nil, nil, ErrExecute
				}
				length, p = uint64(p[0]), p[1:]
			} else {
				var ok bool
				length, p, ok = readLength(p)
				if !ok {
					return nil, nil, ErrExecute
				}
			}
			if length > uint64(len(p)) {
				return nil, nil, ErrExecute
			}
			v.Bytes, p = p[:int(length)], p[int(length):]
		}
		if !validValue(v) {
			return nil, nil, ErrExecute
		}
		values[i] = v
	}
	if len(p) != 0 {
		return nil, nil, ErrExecute
	}
	return values, types, nil
}

func readLength(b []byte) (uint64, []byte, bool) {
	if len(b) == 0 {
		return 0, nil, false
	}
	n := 0
	switch b[0] {
	case 251, 255:
		return 0, nil, false // NULL is carried by the bitmap, not here.
	case 252:
		n = 2
	case 253:
		n = 3
	case 254:
		n = 8
	default:
		return uint64(b[0]), b[1:], true
	}
	if len(b) < n+1 {
		return 0, nil, false
	}
	var length uint64
	for i := 0; i < n; i++ {
		length |= uint64(b[1+i]) << uint(8*i)
	}
	return length, b[n+1:], true
}

// EncodeBinaryRow encodes exact typed cells with the result-row null bitmap's
// two-bit offset. limit is the existing wire packet budget, not a new product
// capacity. Validation and accounting finish before allocating the row. The
// caller must independently match types/unsigned flags to current metadata.
func EncodeBinaryRow(values []Value, limit int) ([]byte, error) {
	if len(values) == 0 || len(values) > 65535 || limit < 1 || limit > MaxEnvelope {
		return nil, ErrValue
	}
	n := 1 + (len(values)+9)/8
	for _, v := range values {
		if !validValue(v) {
			return nil, ErrValue
		}
		if v.Null {
			continue
		}
		length := len(v.Bytes)
		if length > limit-n {
			return nil, ErrValue
		}
		switch valueShape(v.Type) {
		case -1:
			length += lengthPrefixSize(uint64(length))
		case -2:
			length++
		}
		if length > limit-n {
			return nil, ErrValue
		}
		n += length
	}
	if n > limit {
		return nil, ErrValue
	}
	maskSize := (len(values) + 9) / 8
	b := make([]byte, 1+maskSize, n)
	for i, v := range values {
		if v.Null {
			b[1+(i+2)/8] |= 1 << uint((i+2)%8)
			continue
		}
		switch valueShape(v.Type) {
		case -1:
			b = appendLength(b, uint64(len(v.Bytes)))
		case -2:
			b = append(b, byte(len(v.Bytes)))
		}
		b = append(b, v.Bytes...)
	}
	return b, nil
}

func lengthPrefixSize(n uint64) int {
	switch {
	case n < 251:
		return 1
	case n < 1<<16:
		return 3
	case n < 1<<24:
		return 4
	default:
		return 9
	}
}

func appendLength(b []byte, n uint64) []byte {
	switch lengthPrefixSize(n) {
	case 1:
		return append(b, byte(n))
	case 3:
		return binary.LittleEndian.AppendUint16(append(b, 252), uint16(n))
	case 4:
		return append(b, 253, byte(n), byte(n>>8), byte(n>>16))
	default:
		return binary.LittleEndian.AppendUint64(append(b, 254), n)
	}
}
