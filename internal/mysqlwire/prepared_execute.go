package mysqlwire

import (
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

func (s *preparedSession) executeStatement(payload []byte, call preparedCall) ([][]byte, error) {
	if !s.execute {
		return [][]byte{ErrorPacket(1235, "42000", "prepared execution is not implemented")}, nil
	}
	if len(payload) < 4 {
		return [][]byte{ErrorPacket(1835, "HY000", "Malformed communication packet")}, nil
	}
	id := binary.LittleEndian.Uint32(payload)
	e, ok := s.registry.Lookup(id)
	if !ok {
		return [][]byte{ErrorPacket(1243, "HY000", fmt.Sprintf("Unknown prepared statement handler (%d) given to mysqld_stmt_execute", id))}, nil
	}
	values, types, err := preparedproto.DecodeExecute(payload, e.Parameters, s.types[id])
	if err != nil {
		if errors.Is(err, preparedproto.ErrCursor) {
			return [][]byte{ErrorPacket(1235, "42000", err.Error())}, nil
		}
		return [][]byte{ErrorPacket(1835, "HY000", "Malformed communication packet")}, nil
	}
	body, err := preparedproto.EncodeValues(values)
	if err != nil {
		return nil, err
	}
	r, err := s.call(preparedproto.Execute, e.Handle, body, true, call)
	if err != nil {
		return nil, err
	}
	// The engine has consumed these bindings even when SQL execution fails.
	// Never commit a cache from a structurally invalid request or failed call.
	s.types[id] = types
	if !r.OK {
		return packets(r)
	}
	if r.StatementID != e.Handle {
		return nil, errors.New("prepared execute handle mismatch")
	}
	return preparedResultPackets(r)
}

// Only the single-result P2 shape is accepted here; P3 adds explicit chains.
// A text/partially typed response must never be mistaken for a binary result.
func preparedResultPackets(r guest.Result) ([][]byte, error) {
	if !r.OK || !r.BinaryRows || r.Results != nil || r.Status&8 != 0 {
		return nil, errors.New("invalid prepared binary result envelope")
	}
	if r.Columns == nil {
		if r.Rows != nil {
			return nil, errors.New("prepared DML unexpectedly contains rows")
		}
		return packets(r)
	}
	if len(r.Columns) == 0 || len(r.Columns) > 65535 {
		return nil, errors.New("invalid prepared result metadata count")
	}
	out := [][]byte{leint(uint64(len(r.Columns)))}
	for _, c := range r.Columns {
		b, err := preparedColumn(c)
		if err != nil {
			return nil, err
		}
		out = append(out, b)
	}
	out = append(out, eofPacket(r.Status, 0))
	for _, row := range r.Rows {
		if len(row) != len(r.Columns) {
			return nil, errors.New("prepared result row width mismatch")
		}
		values := make([]preparedproto.Value, len(row))
		for i, cell := range row {
			c := r.Columns[i]
			values[i] = preparedproto.Value{ParameterType: preparedproto.ParameterType{Type: c.Type, Unsigned: c.Flags&32 != 0}, Null: cell == nil}
			if cell != nil {
				// Reject an excessive hex field before allocating its byte copy.
				if len(cell.Hex) > 2*maxPacket {
					return nil, errors.New("prepared cell exceeds packet limit")
				}
				var err error
				values[i].Bytes, err = hex.DecodeString(cell.Hex)
				if err != nil {
					return nil, err
				}
			}
		}
		b, err := preparedproto.EncodeBinaryRow(values, maxPacket)
		if err != nil {
			return nil, err
		}
		out = append(out, b)
	}
	return append(out, eofPacket(r.Status, r.Warnings)), nil
}
