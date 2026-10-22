package mysqlwire

import (
	"encoding/binary"
	"errors"

	"github.com/masahitojp/mariamem/internal/preparedproto"
)

// SEND_LONG_DATA has no client reply, including unknown handles and short
// packets. An internal ack serializes engine ownership before the next command;
// the disconnect/read-ahead monitor must not consume that next command.
func (s *preparedSession) sendLongData(payload []byte, call preparedCall) ([][]byte, error) {
	if s == nil || len(payload) < 6 {
		return [][]byte{}, nil
	}
	id := binary.LittleEndian.Uint32(payload)
	e, ok := s.registry.Lookup(id)
	if !ok {
		return [][]byte{}, nil
	}
	if !s.longData {
		return nil, errors.New("prepared guest does not implement LONG_DATA")
	}
	r, err := s.call(preparedproto.LongData, e.Handle, payload[4:], false, call)
	if err != nil {
		return nil, err
	}
	if r.BinaryRows || r.Parameters != nil || r.Columns != nil || r.Rows != nil || r.StatementID != 0 || r.ParamCount != 0 {
		return nil, errors.New("invalid prepared LONG_DATA acknowledgement")
	}
	index := binary.LittleEndian.Uint16(payload[4:])
	if !r.OK {
		// The public embedded API rejects an invalid parameter immediately. The
		// authored guest retains native wire's deferred error until RESET/CLOSE.
		_, alreadyDeferred := s.longErrors[id]
		if r.Errno != 1210 || r.SQLState != "HY000" || (index < e.Parameters && !alreadyDeferred) {
			return nil, errors.New("unexpected prepared LONG_DATA failure")
		}
		s.longErrors[id] = r
		return [][]byte{}, nil
	}
	if index >= e.Parameters {
		return nil, errors.New("LONG_DATA accepted an invalid parameter")
	}
	if s.long[id] == nil {
		s.long[id] = make(map[uint16]bool)
	}
	s.long[id][index] = true
	return [][]byte{}, nil
}
