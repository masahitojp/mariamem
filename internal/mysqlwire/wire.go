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

const capabilities uint32 = 1 | 4 | 8 | 512 | 8192 | 32768 | 524288
const maxPacket = 0xffffff - 1

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

// callQuery observes a driver disconnect while the guest is executing SQL.
// MySQL clients issue one command at a time; unexpected pipelined input also
// invalidates the instance rather than leaving a query running unsupervised.
func (w *wire) callQuery(p *guest.Process, slot uint32, sql []byte) (guest.Result, error) {
	ctx, cancel := context.WithTimeout(context.Background(), w.timeout)
	defer cancel()
	type outcome struct {
		result guest.Result
		err    error
	}
	completed := make(chan outcome, 1)
	go func() {
		r, err := p.Call(ctx, 2, slot, sql)
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
	defer func() {
		activity.Cleanup()
		r, e := call(3, nil)
		if e != nil {
			err = errors.Join(err, e)
		} else if !r.Closed {
			err = errors.Join(err, errors.New("session did not close"))
		}
	}()
	w := wire{conn: conn, timeout: timeout, begin: activity.Begin}
	query := func(sql []byte, monitor bool) (guest.Result, error) {
		if len(sql) == 0 || len(sql) > 1<<20 {
			return guest.Result{Errno: 1153, SQLState: "08S01", Error: "SQL length must be 1..1048576 bytes"}, nil
		}
		var r guest.Result
		var e error
		if monitor {
			r, e = w.callQuery(p, slot, sql)
		} else {
			r, e = call(2, sql)
		}
		if e == nil && r.Version != 2 {
			e = errors.New("unexpected guest query version")
		}
		return r, e
	}
	r, err = query([]byte("SELECT CONNECTION_ID()"), false)
	if err != nil {
		return err
	}
	if !r.OK || len(r.Rows) != 1 || len(r.Rows[0]) != 1 || r.Rows[0][0] == nil {
		return errors.New("invalid connection ID response")
	}
	idBytes, err := hex.DecodeString(r.Rows[0][0].Hex)
	if err != nil {
		return err
	}
	id, err := strconv.ParseUint(string(idBytes), 10, 32)
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
	b := append([]byte("\x0a13.1.0-MariaDB-mariamem\x00"), le32(uint32(id))...)
	b = append(b, salt[:8]...)
	b = append(b, 0)
	b = append(b, le16(uint16(capabilities&0xffff))...)
	b = append(b, 45)
	b = append(b, le16(status)...)
	b = append(b, le16(uint16(capabilities>>16))...)
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
	if flags&512 == 0 || flags&(2|2048|65536) != 0 {
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
		case 1:
			return nil
		case 3:
			r, e = query(request[1:], true)
		case 2:
			r, e = use(request[1:], true)
		case 14:
			replies = [][]byte{okPacket(status, 0, 0, 0)}
		default:
			replies = [][]byte{ErrorPacket(1235, "42000", "command is not supported")}
		}
		if e != nil {
			_ = w.send(fatalPacket(e))
			return e
		}
		if replies == nil {
			if r.Version == 2 {
				status = r.Status
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
