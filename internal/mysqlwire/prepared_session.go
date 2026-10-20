package mysqlwire

import (
	"encoding/binary"
	"errors"
	"fmt"
	"slices"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

// preparedSession is confined to the owning TCP session's serial dispatcher.
// A nil owner preserves the unsupported contract of the old canonical guest.
type preparedSession struct {
	registry *preparedproto.Registry
	status   uint16
}

func newPreparedSession(open guest.Result, readyVersion int, readyOperations []uint8) (*preparedSession, error) {
	if open.PreparedVersion != readyVersion || !slices.Equal(open.PreparedOperations, readyOperations) {
		return nil, errors.New("prepared Ready/open advertisement mismatch")
	}
	if open.PreparedVersion == 0 && open.SessionGeneration == 0 && len(open.PreparedOperations) == 0 {
		return nil, nil
	}
	if !open.OK || open.Version != 2 || open.PreparedVersion != preparedproto.Version {
		return nil, errors.New("prepared open schema mismatch")
	}
	ops := make(map[byte]bool)
	for _, op := range open.PreparedOperations {
		if op < preparedproto.Prepare || op > preparedproto.Reset || ops[op] {
			return nil, errors.New("invalid prepared operation advertisement")
		}
		ops[op] = true
	}
	for _, op := range []byte{preparedproto.Prepare, preparedproto.Close, preparedproto.Reset} {
		if !ops[op] {
			return nil, errors.New("missing prepared lifecycle operation")
		}
	}
	r, err := preparedproto.NewRegistry(open.SessionGeneration)
	if err != nil {
		return nil, err
	}
	return &preparedSession{registry: r, status: open.Status}, nil
}

// call's monitor is false only for no-response operations: a following packet
// may already be queued. The transport call still has the session deadline.
type preparedCall func([]byte, bool) (guest.Result, error)

func (s *preparedSession) call(op byte, handle uint32, payload []byte, monitor bool, call preparedCall) (guest.Result, error) {
	b, err := preparedproto.Encode(preparedproto.Request{Operation: op, Generation: s.registry.Generation(), Handle: handle, Payload: payload})
	if err != nil {
		return guest.Result{}, err
	}
	r, err := call(b, monitor)
	if err != nil {
		return guest.Result{}, err
	}
	if err = validatePrepared(r, s.registry.Generation()); err != nil {
		return guest.Result{}, err
	}
	s.status = r.Status &^ 8
	return r, nil
}

func (s *preparedSession) handle(op byte, payload []byte, call preparedCall) ([][]byte, error) {
	if s == nil {
		return [][]byte{ErrorPacket(1235, "42000", "command is not supported")}, nil
	}
	if op == preparedproto.Prepare {
		if len(payload) == 0 || len(payload) > preparedproto.MaxSQL {
			return [][]byte{ErrorPacket(1153, "08S01", "prepared SQL length must be 1..1048576 bytes")}, nil
		}
		r, err := s.call(op, 0, payload, true, call)
		if err != nil {
			return nil, err
		}
		if !r.OK {
			return packets(r)
		}
		// Validate all metadata before installing any client-visible mapping.
		replies, err := preparePackets(r, s.registry.Generation(), 1)
		if err == nil {
			var id uint32
			id, err = s.registry.Add(r.SessionGeneration, r.StatementID, r.ParamCount)
			if err == nil {
				binary.LittleEndian.PutUint32(replies[0][1:], id)
				return replies, nil
			}
		}
		if r.StatementID != 0 {
			closed, closeErr := s.call(preparedproto.Close, r.StatementID, nil, false, call)
			if closeErr != nil {
				return nil, errors.Join(err, closeErr)
			}
			if !closed.OK {
				return nil, errors.Join(err, errors.New("prepared metadata unwind did not close native handle"))
			}
		}
		return nil, err
	}
	if op != preparedproto.Close && op != preparedproto.Reset {
		return [][]byte{ErrorPacket(1235, "42000", "prepared execution is not implemented")}, nil
	}
	if len(payload) != 4 {
		// CLOSE never sends a client reply; a malformed CLOSE is a framing error.
		if op == preparedproto.Close {
			return nil, errors.New("invalid statement close packet")
		}
		return [][]byte{ErrorPacket(1835, "HY000", "Malformed communication packet")}, nil
	}
	id := binary.LittleEndian.Uint32(payload)
	e, ok := s.registry.Lookup(id)
	if !ok {
		if op == preparedproto.Close {
			return [][]byte{}, nil
		}
		return [][]byte{ErrorPacket(1243, "HY000", fmt.Sprintf("Unknown prepared statement handler (%d) given to mysqld_stmt_reset", id))}, nil
	}
	r, err := s.call(op, e.Handle, nil, op != preparedproto.Close, call)
	if err != nil {
		return nil, err
	}
	if op == preparedproto.Close {
		if !r.OK {
			return nil, errors.New("native prepared close failed")
		}
		s.registry.Remove(id)
		return [][]byte{}, nil
	}
	if !r.OK {
		return packets(r)
	}
	return [][]byte{okPacket(r.Status, 0, 0, r.Warnings)}, nil
}
