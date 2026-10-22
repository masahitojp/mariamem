// Package mysqlwire provides the initial MySQL text protocol.
package mysqlwire

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net"
	"strconv"
	"strings"
	"time"

	"github.com/masahitojp/mariamem/internal/guest"
)

const capabilities uint32 = 1 | 4 | 8 | 512 | 8192 | 32768 | 65536 | 131072 | 524288
const maxPacket = 0xffffff - 1
const clientFoundRows uint32 = 2
const clientPSMultiResults uint32 = 1 << 18

func preparedCapabilities(s *preparedSession) uint32 {
	if s != nil && s.execute {
		return capabilities | clientPSMultiResults
	}
	return capabilities
}

type wire struct {
	conn     net.Conn
	sequence byte
	timeout  time.Duration
	begin    func() bool
}

func (w *wire) read(idle bool) ([]byte, error) {
	var h [4]byte
	if idle {
		w.conn.SetReadDeadline(time.Time{})
	} else {
		w.conn.SetReadDeadline(time.Now().Add(w.timeout))
	}
	if _, err := io.ReadFull(w.conn, h[:1]); err != nil {
		return nil, err
	}
	if idle && w.begin != nil && !w.begin() {
		return nil, errors.New("database is stopping")
	}
	w.conn.SetReadDeadline(time.Now().Add(w.timeout))
	if _, err := io.ReadFull(w.conn, h[1:]); err != nil {
		return nil, err
	}
	n := int(h[0]) | int(h[1])<<8 | int(h[2])<<16
	if h[3] != w.sequence || n == 0 || n > 1048577 {
		return nil, errors.New("invalid MySQL frame")
	}
	w.sequence++
	b := make([]byte, n)
	_, err := io.ReadFull(w.conn, b)
	return b, err
}
func (w *wire) send(b []byte) error {
	if len(b) > maxPacket {
		return errors.New("MySQL response packet too large")
	}
	w.conn.SetWriteDeadline(time.Now().Add(w.timeout))
	n := len(b)
	frame := append([]byte{byte(n), byte(n >> 8), byte(n >> 16), w.sequence}, b...)
	w.sequence++
	for len(frame) > 0 {
		n, err := w.conn.Write(frame)
		if err != nil {
			return err
		}
		if n == 0 {
			return io.ErrShortWrite
		}
		frame = frame[n:]
	}
	return nil
}

// callGuest observes a driver disconnect while the guest is executing SQL.
// MySQL clients issue one command at a time; unexpected pipelined input also
// invalidates the instance rather than leaving a query running unsupervised.
func (w *wire) callGuest(p *guest.Process, op byte, slot uint32, sql []byte) (guest.Result, error) {
	ctx, cancel := context.WithTimeout(context.Background(), w.timeout)
	defer cancel()
	type outcome struct {
		result guest.Result
		err    error
	}
	completed := make(chan outcome, 1)
	go func() {
		r, err := p.Call(ctx, op, slot, sql)
		completed <- outcome{r, err}
	}()
	type observed struct {
		n   int
		err error
	}
	reading := make(chan observed, 1)
	_ = w.conn.SetReadDeadline(time.Time{})
	go func() {
		var b [1]byte
		n, err := w.conn.Read(b[:])
		reading <- observed{n, err}
	}()
	var result outcome
	select {
	case seen := <-reading:
		var cause error = errors.New("SQL client disconnected during query")
		if seen.err != nil {
			cause = fmt.Errorf("SQL client disconnected during query: %w", seen.err)
		}
		if seen.n != 0 {
			cause = errors.New("unexpected client input during running query")
		}
		p.Abort(cause)
		<-completed
		return guest.Result{}, cause
	case result = <-completed:
		_ = w.conn.SetReadDeadline(time.Now())
		seen := <-reading
		if seen.n != 0 {
			cause := errors.New("unexpected client input during running query")
			p.Abort(cause)
			return guest.Result{}, cause
		} else if seen.err != nil {
			var timeout net.Error
			if !errors.As(seen.err, &timeout) || !timeout.Timeout() {
				cause := fmt.Errorf("SQL client disconnected during query: %w", seen.err)
				p.Abort(cause)
				return guest.Result{}, cause
			}
		}
	}
	_ = w.conn.SetReadDeadline(time.Time{})
	return result.result, result.err
}

// SET_OPTION has two standard values. Validate its wire domain before calling
// the embedded API, whose invalid-option failure does not populate MYSQL errno.
func setOptionError(payload []byte) []byte {
	if len(payload) != 2 {
		return ErrorPacket(1235, "HY000", "invalid set-option packet")
	}
	if binary.LittleEndian.Uint16(payload) > 1 {
		return ErrorPacket(1047, "08S01", "Unknown command")
	}
	return nil
}
func le16(n uint16) []byte { return []byte{byte(n), byte(n >> 8)} }
func le32(n uint32) []byte { return []byte{byte(n), byte(n >> 8), byte(n >> 16), byte(n >> 24)} }
func leint(n uint64) []byte {
	switch {
	case n < 251:
		return []byte{byte(n)}
	case n <= 0xffff:
		return append([]byte{0xfc}, le16(uint16(n))...)
	case n <= 0xffffff:
		return []byte{0xfd, byte(n), byte(n >> 8), byte(n >> 16)}
	}
	b := make([]byte, 9)
	b[0] = 0xfe
	binary.LittleEndian.PutUint64(b[1:], n)
	return b
}
func lestr(b []byte) []byte { return append(leint(uint64(len(b))), b...) }
func ErrorPacket(code uint16, state, message string) []byte {
	if len(state) != 5 {
		state = "HY000"
	}
	b := append([]byte{0xff}, le16(code)...)
	return append(b, []byte("#"+state+message)...)
}

// A transport/serialization failure closes a no-response command's session;
// it must not leave an invented error packet for the next PING/EXECUTE to read.
func (w *wire) commandFailure(op byte, err error) error {
	if op != 24 && op != 25 {
		_ = w.send(fatalPacket(err))
	}
	return err
}

func fatalPacket(err error) []byte {
	if errors.Is(err, context.DeadlineExceeded) {
		return ErrorPacket(2013, "HY000", "mariamem query timed out; database instance terminated")
	}
	return ErrorPacket(2013, "HY000", "mariamem database instance terminated: "+err.Error())
}
func RejectCapacity(conn net.Conn) {
	w := wire{conn: conn, timeout: time.Second}
	_ = w.send(ErrorPacket(1040, "08004", "mariamem session capacity exhausted"))
	conn.Close()
}
func RejectUnavailable(conn net.Conn) {
	w := wire{conn: conn, timeout: time.Second}
	_ = w.send(ErrorPacket(2013, "HY000", "mariamem database instance terminated"))
	conn.Close()
}
func okPacket(status uint16, affected, id uint64, warnings uint16) []byte {
	b := append([]byte{0}, leint(affected)...)
	b = append(b, leint(id)...)
	b = append(b, le16(status)...)
	return append(b, le16(warnings)...)
}
func eofPacket(status, warnings uint16) []byte {
	return append(append([]byte{0xfe}, le16(warnings)...), le16(status)...)
}
func packets(r guest.Result) ([][]byte, error) {
	if r.Results != nil {
		if !r.OK || len(r.Results) == 0 {
			return nil, errors.New("invalid multi-result envelope")
		}
		var replies [][]byte
		for i, part := range r.Results {
			if part.Version != 2 || part.Results != nil || (!part.OK && i != len(r.Results)-1) {
				return nil, errors.New("invalid multi-result element")
			}
			part.Status &^= 8
			if i < len(r.Results)-1 {
				part.Status |= 8
			}
			next, err := packets(part)
			if err != nil {
				return nil, err
			}
			replies = append(replies, next...)
		}
		return replies, nil
	}

	if !r.OK {
		return [][]byte{ErrorPacket(r.Errno, r.SQLState, r.Error)}, nil
	}
	if r.Columns == nil {
		a, e := strconv.ParseUint(r.Affected, 10, 64)
		if e != nil {
			return nil, e
		}
		id, e := strconv.ParseUint(r.InsertID, 10, 64)
		if e != nil {
			return nil, e
		}
		return [][]byte{okPacket(r.Status, a, id, r.Warnings)}, nil
	}
	result := [][]byte{leint(uint64(len(r.Columns)))}
	for _, c := range r.Columns {
		var b []byte
		for _, name := range []string{c.Catalog, c.DB, c.Table, c.OrgTable, c.Name, c.OrgName} {
			b = append(b, lestr([]byte(name))...)
		}
		b = append(b, 12)
		b = append(b, le16(c.Charset)...)
		b = append(b, le32(c.Length)...)
		b = append(b, c.Type)
		b = append(b, le16(c.Flags)...)
		b = append(b, c.Decimals, 0, 0)
		result = append(result, b)
	}
	result = append(result, eofPacket(r.Status, 0))
	for _, row := range r.Rows {
		if len(row) != len(r.Columns) {
			return nil, errors.New("guest row width mismatch")
		}
		var b []byte
		for _, cell := range row {
			if cell == nil {
				b = append(b, 0xfb)
			} else {
				value, err := hex.DecodeString(cell.Hex)
				if err != nil {
					return nil, err
				}
				b = append(b, lestr(value)...)
			}
		}
		result = append(result, b)
	}
	result = append(result, eofPacket(r.Status, r.Warnings))
	for _, b := range result {
		if len(b) > maxPacket {
			return [][]byte{ErrorPacket(1153, "08S01", "result exceeds packet limit")}, nil
		}
	}
	return result, nil
}
func takeString(b []byte) ([]byte, []byte, error) {
	i := bytes.IndexByte(b, 0)
	if i < 0 {
		return nil, nil, errors.New("unterminated auth field")
	}
	return b[:i], b[i+1:], nil
}

// Serve owns one MYSQL session. A TCP close does not shut down the engine.
type Activity struct {
	Begin   func() bool
	Idle    func(uint16)
	Cleanup func()
}

func connectionIdentity(r guest.Result) (uint32, []byte, error) {
	if !r.OK || len(r.Rows) != 1 || len(r.Rows[0]) != 2 || r.Rows[0][0] == nil || r.Rows[0][1] == nil {
		return 0, nil, errors.New("invalid connection identity response")
	}
	idBytes, err := hex.DecodeString(r.Rows[0][0].Hex)
	if err != nil {
		return 0, nil, err
	}
	id, err := strconv.ParseUint(string(idBytes), 10, 32)
	if err != nil {
		return 0, nil, err
	}
	serverVersion, err := hex.DecodeString(r.Rows[0][1].Hex)
	if err != nil {
		return 0, nil, err
	}
	if len(serverVersion) == 0 || bytes.IndexByte(serverVersion, 0) >= 0 {
		return 0, nil, errors.New("invalid server version response")
	}
	return uint32(id), serverVersion, nil
}

func Serve(conn net.Conn, p *guest.Process, slot uint32, timeout time.Duration, closing func() bool, activity Activity) (err error) {
	call := func(op byte, sql []byte) (guest.Result, error) {
		ctx, cancel := context.WithTimeout(context.Background(), timeout)
		defer cancel()
		return p.Call(ctx, op, slot, sql)
	}
	r, err := call(1, nil)
	if err != nil {
		_ = (&wire{conn: conn, timeout: timeout}).send(fatalPacket(err))
		return err
	}
	if !r.OK {
		return fmt.Errorf("open session: %s", r.Error)
	}
	preparedOpen := r
	opened := true
	defer func() {
		if !opened {
			return
		}
		activity.Cleanup()
		r, e := call(3, nil)
		if e != nil {
			err = errors.Join(err, e)
		} else if !r.Closed {
			err = errors.Join(err, errors.New("session did not close"))
		}
	}()
	// Validate Ready/open before advertising prepared result support. A legacy
	// guest and the staged PREPARE-only owner must not advertise PS results.
	statements, err := newPreparedSession(preparedOpen, p.PreparedVersion, p.PreparedOperations)
	if err != nil {
		return err
	}
	w := wire{conn: conn, timeout: timeout, begin: activity.Begin}
	query := func(sql []byte, monitor bool) (guest.Result, error) {
		if len(sql) == 0 || len(sql) > 1<<20 {
			return guest.Result{Errno: 1153, SQLState: "08S01", Error: "SQL length must be 1..1048576 bytes"}, nil
		}
		var r guest.Result
		var e error
		if monitor {
			r, e = w.callGuest(p, 2, slot, sql)
		} else {
			r, e = call(2, sql)
		}
		if e == nil && r.Version != 2 {
			e = errors.New("unexpected guest query version")
		}
		return r, e
	}
	// Read the identity from this guest/session so guest upgrades cannot leave
	// a stale server version in the handshake. Keep this a single query.
	r, err = query([]byte("SELECT CONNECTION_ID(), VERSION()"), false)
	if err != nil {
		return err
	}
	id, serverVersion, err := connectionIdentity(r)
	if err != nil {
		return err
	}
	status := r.Status
	salt := make([]byte, 20)
	if _, err = rand.Read(salt); err != nil {
		return err
	}
	for i := range salt {
		salt[i] = 33 + salt[i]%90
	}
	serverCaps := preparedCapabilities(statements)
	b := append([]byte{10}, serverVersion...)
	b = append(b, 0)
	b = append(b, le32(uint32(id))...)
	b = append(b, salt[:8]...)
	b = append(b, 0)
	b = append(b, le16(uint16(serverCaps&0xffff))...)
	b = append(b, 45)
	b = append(b, le16(status)...)
	b = append(b, le16(uint16(serverCaps>>16))...)
	b = append(b, 21)
	b = append(b, make([]byte, 10)...)
	b = append(b, salt[8:]...)
	b = append(b, 0)
	b = append(b, []byte("mysql_native_password\x00")...)
	if e := w.send(b); e != nil {
		return nil
	}
	auth, e := w.read(false)
	if e != nil {
		return nil
	}
	if len(auth) < 34 {
		_ = w.send(ErrorPacket(1045, "28000", "invalid handshake"))
		return nil
	}
	flags := binary.LittleEndian.Uint32(auth)
	if flags&512 == 0 || flags&2048 != 0 {
		_ = w.send(ErrorPacket(1235, "42000", "unsupported connection capabilities"))
		return nil
	}
	user, rest, e := takeString(auth[32:])
	if e != nil {
		return nil
	}
	var password []byte
	if flags&32768 != 0 {
		if len(rest) < 1 || int(rest[0]) > len(rest)-1 {
			return nil
		}
		n := int(rest[0])
		password = rest[1 : 1+n]
		rest = rest[1+n:]
	} else {
		password, rest, e = takeString(rest)
		if e != nil {
			return nil
		}
	}
	if string(user) != "root" || len(password) != 0 {
		_ = w.send(ErrorPacket(1045, "28000", "only local root with empty password is supported"))
		return nil
	}
	if flags&clientFoundRows != 0 {
		// MariaDB's client capability is fixed at connect time. Reopen only this
		// flagged session so unflagged clients retain single-statement behavior.
		// MULTI_STATEMENTS also requires result draining; never merely accept its bit.
		closed, closeErr := call(3, nil)
		if closeErr != nil || !closed.Closed {
			if closeErr == nil {
				closeErr = errors.New("guest session did not close before FOUND_ROWS reopen")
			}
			_ = w.send(fatalPacket(closeErr))
			return closeErr
		}
		opened = false
		r, err = call(1, []byte{1})
		if err != nil {
			_ = w.send(fatalPacket(err))
			return err
		}
		if !r.OK {
			_ = w.send(ErrorPacket(r.Errno, r.SQLState, r.Error))
			return nil
		}
		opened = true
		status = r.Status
		preparedOpen = r
		statements, err = newPreparedSession(preparedOpen, p.PreparedVersion, p.PreparedOperations)
		if err != nil {
			return err
		}
	}
	if statements != nil {
		statements.psMulti = flags&clientPSMultiResults != 0
		defer statements.registry.Clear()
	}
	// Embedded CLIENT_CAPABILITIES already includes MULTI_RESULTS. Toggle
	// MULTI_STATEMENTS through its public API without replacing the MYSQL/THD
	// whose identity was sent in the greeting (libmysqld/client_settings.h).
	if flags&65536 != 0 {
		r, err = call(4, []byte{0, 0})
		if err != nil {
			return err
		}
		if r.Version != 2 {
			return errors.New("set-option bridge version mismatch")
		}
		if !r.OK {
			if r.Errno == 0 {
				return errors.New("embedded option API failed without error details")
			}
			_ = w.send(ErrorPacket(r.Errno, r.SQLState, r.Error))
			return nil
		}
		status = r.Status
	}
	use := func(name []byte, monitor bool) (guest.Result, error) {
		return query([]byte("USE `"+strings.ReplaceAll(string(name), "`", "``")+"`"), monitor)
	}
	if flags&8 != 0 {
		name, _, e := takeString(rest)
		if e != nil {
			return nil
		}
		r, e := use(name, false)
		if e != nil {
			return e
		}
		status = r.Status
		if !r.OK {
			_ = w.send(ErrorPacket(r.Errno, r.SQLState, r.Error))
			return nil
		}
	}
	if e := w.send(okPacket(status, 0, 0, 0)); e != nil {
		return nil
	}
	activity.Idle(status)
	for !closing() {
		w.sequence = 0
		request, e := w.read(true)
		if e != nil {
			return nil
		}
		if closing() {
			return nil
		}
		var replies [][]byte
		switch request[0] {
		case 22, 23, 24, 25, 26:
			// Local errors and ignored unknown CLOSE must preserve state from the
			// most recent text command too (not an older prepared response).
			if statements != nil {
				statements.status = status
			}
			replies, e = statements.handle(request[0], request[1:], func(body []byte, monitor bool) (guest.Result, error) {
				if monitor {
					return w.callGuest(p, 5, slot, body)
				}
				return call(5, body)
			})
			if statements != nil {
				status = statements.status
			}
		case 1:
			return nil
		case 3:
			r, e = query(request[1:], true)
		case 2:
			r, e = use(request[1:], true)
		case 27:
			if bad := setOptionError(request[1:]); bad != nil {
				replies = [][]byte{bad}
				break
			}
			r, e = w.callGuest(p, 4, slot, request[1:])
			if e == nil && r.Version != 2 {
				e = errors.New("text option bridge version mismatch")
			}
			if e == nil && !r.OK && r.Errno == 0 {
				e = errors.New("embedded option API failed without error details")
			}
			if e == nil && r.OK {
				status = r.Status &^ 8
				replies = [][]byte{eofPacket(status, r.Warnings)}
			}
		case 14:
			replies = [][]byte{okPacket(status, 0, 0, 0)}
		default:
			replies = [][]byte{ErrorPacket(1235, "42000", "command is not supported")}
		}
		if e != nil {
			return w.commandFailure(request[0], e)
		}
		if replies == nil {
			if r.Version == 2 {
				status = r.Status &^ 8
			}
			replies, e = packets(r)
			if e != nil {
				return e
			}
		}
		for _, reply := range replies {
			if e := w.send(reply); e != nil {
				return nil
			}
		}
		activity.Idle(status)
	}
	return nil
}
