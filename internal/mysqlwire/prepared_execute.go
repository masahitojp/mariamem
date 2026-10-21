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

// Binary results retain each native status, including OUT and MORE_RESULTS.
// Validate the entire chain before returning any packet to the connection.
func preparedResultPackets(r guest.Result) ([][]byte, error) {
	if r.Results != nil {
		if !r.OK || !r.BinaryRows || len(r.Results) == 0 || r.Status&8 != 0 || r.Columns != nil || r.Rows != nil {
			return nil, errors.New("invalid prepared result chain")
		}
		var replies [][]byte
		for i, part := range r.Results {
			more := i < len(r.Results)-1
			if part.Version != 2 || part.Results != nil || (part.Status&8 != 0) != more || (!part.OK && more) {
				return nil, errors.New("invalid prepared result chain element")
			}
			var next [][]byte
			var err error
			if !part.OK {
				if part.Errno == 0 || len(part.SQLState) != 5 || part.Columns != nil || part.Rows != nil {
					return nil, errors.New("invalid prepared terminal error")
				}
				next, err = packets(part)
			} else {
				if part.StatementID != r.StatementID {
					return nil, errors.New("prepared result chain handle mismatch")
				}
				next, err = preparedSingleResultPackets(part, true)
			}
			if err != nil {
				return nil, err
			}
			replies = append(replies, next...)
		}
		return replies, nil
	}
	return preparedSingleResultPackets(r, false)
}

func preparedSingleResultPackets(r guest.Result, allowMore bool) ([][]byte, error) {
	if !r.OK || !r.BinaryRows || r.Results != nil || (!allowMore && r.Status&8 != 0) {
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
