package host

import (
	"encoding/binary"
	"net"
	"time"
)

// RejectCapacity writes a bounded MySQL ERR packet (errno 1040, SQLSTATE 08004)
// and closes a pre-login TCP connection when all 16 session slots are occupied.
func RejectCapacity(conn net.Conn) {
	defer conn.Close()
	_ = conn.SetWriteDeadline(time.Now().Add(time.Second))
	const msg = "#08004mariamem session capacity exhausted"
	payload := make([]byte, 3+len(msg))
	payload[0] = 0xff
	binary.LittleEndian.PutUint16(payload[1:3], 1040)
	copy(payload[3:], msg)
	frame := make([]byte, 4+len(payload))
	n := len(payload)
	frame[0], frame[1], frame[2], frame[3] = byte(n), byte(n>>8), byte(n>>16), 0
	copy(frame[4:], payload)
	_, _ = conn.Write(frame)
}
