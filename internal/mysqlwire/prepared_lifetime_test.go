package mysqlwire

import (
	"encoding/binary"
	"errors"
	"testing"

	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

func TestPreparedLifecycleNativeShortAndSurplusBodies(t *testing.T) {
	for _, op := range []byte{preparedproto.Close, preparedproto.Reset} {
		for size := 0; size <= 8; size++ {
			s, _ := newPreparedSession(preparedOpen(7), 1, []uint8{22, 25, 26})
			id, _ := s.registry.Add(7, 91, 1)
			s.types[id] = []preparedproto.ParameterType{{Type: 3}}
			body := make([]byte, size)
			if size > 0 {
				body[0] = byte(id)
			}
			for i := 4; i < size; i++ {
				body[i] = 0xff
			}
			calls := 0
			packets, err := s.handle(op, body, func(data []byte, monitor bool) (guest.Result, error) {
				r, e := preparedproto.Decode(data)
				if e != nil {
					t.Fatal(e)
				}
				if r.Operation != op || r.Handle != 91 || r.Generation != 7 || monitor != (op != preparedproto.Close) {
					t.Fatal(r, monitor)
				}
				calls++
				return guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: 7, Status: 3}, nil
			})
			if err != nil {
				t.Fatal(op, size, err)
			}
			if size == 0 {
				if calls != 0 {
					t.Fatal("zero ID reached guest")
				}
				if op == preparedproto.Close && len(packets) != 0 {
					t.Fatal("unknown CLOSE replied")
				}
				if op == preparedproto.Reset && (len(packets) != 1 || binary.LittleEndian.Uint16(packets[0][1:]) != 1243) {
					t.Fatal("unknown RESET lost native error")
				}
			} else {
				if calls != 1 {
					t.Fatal(op, size, calls)
				}
				if op == preparedproto.Close {
					if packets == nil || len(packets) != 0 {
						t.Fatal("CLOSE replied")
					}
					if _, ok := s.registry.Lookup(id); ok || len(s.types) != 0 {
						t.Fatal("CLOSE retained owner/binding")
					}
				} else {
					if len(packets) != 1 || packets[0][0] != 0 || len(s.types) != 1 {
						t.Fatal("RESET lost OK/type reuse")
					}
					if _, ok := s.registry.Lookup(id); !ok {
						t.Fatal("RESET removed statement")
					}
				}
			}
		}
	}
}

func TestPreparedQuotaAndFailedMetadataUnwindNeverInstallOwner(t *testing.T) {
	for _, failure := range []string{"quota", "close-transport", "close-sql-error"} {
		t.Run(failure, func(t *testing.T) {
			s, _ := newPreparedSession(preparedOpen(7), 1, []uint8{22, 25, 26})
			calls := 0
			replies, err := s.handle(22, []byte("SELECT ?"), func(data []byte, monitor bool) (guest.Result, error) {
				req, e := preparedproto.Decode(data)
				if e != nil {
					t.Fatal(e)
				}
				calls++
				r := guest.Result{OK: true, Version: 2, PreparedVersion: 1, SessionGeneration: 7, Status: 2}
				if req.Operation == 22 {
					if !monitor {
						t.Fatal("PREPARE unmonitored")
					}
					if failure == "quota" {
						r.OK = false
						r.Errno = 1461
						r.SQLState = "42000"
						r.Error = "native quota"
						return r, nil
					}
					r.StatementID = 91
					r.Rows = [][]*guest.Cell{{}} // malformed metadata must unwind
					return r, nil
				}
				if req.Operation != 25 || req.Handle != 91 || monitor {
					t.Fatal("unwind did not serialize no-response CLOSE", req, monitor)
				}
				if failure == "close-transport" {
					return guest.Result{}, errors.New("injected close transport failure")
				}
				r.OK = false
				r.Errno = 2008
				r.SQLState = "HY000"
				r.Error = "injected cleanup failure"
				return r, nil
			})
			if failure == "quota" {
				if err != nil || calls != 1 || len(replies) != 1 || binary.LittleEndian.Uint16(replies[0][1:]) != 1461 {
					t.Fatal(replies, calls, err)
				}
			} else if err == nil || replies != nil || calls != 2 {
				t.Fatal("failed cleanup presented as success", replies, calls, err)
			}
			if _, ok := s.registry.Lookup(1); ok {
				t.Fatal("failed PREPARE installed an owner")
			}
			if id, e := s.registry.Add(7, 91, 1); e != nil || id != 1 {
				t.Fatal("failed PREPARE consumed mapping/ID", id, e)
			}
		})
	}
}
