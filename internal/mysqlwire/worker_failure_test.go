package mysqlwire

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"net"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/guest"
)

func TestIdlePingRejectsFailedInstanceWithOriginalCause(t *testing.T) {
	childIn, in := io.Pipe()
	out, childOut := io.Pipe()
	completed := make(chan error, 1)
	writeReply := func(id uint32, result any) error {
		body, _ := json.Marshal(map[string]any{"request_id": id, "result": result})
		frame := make([]byte, 4+len(body))
		binary.LittleEndian.PutUint32(frame, uint32(len(body)))
		copy(frame[4:], body)
		_, err := childOut.Write(frame)
		return err
	}
	go func() {
		defer childOut.Close()
		defer childIn.Close()
		defer func() { completed <- nil }()
		if err := writeReply(0, map[string]any{"ready": true, "api_version": 2, "max_sessions": 16}); err != nil {
			return
		}
		for {
			var header [4]byte
			if _, err := io.ReadFull(childIn, header[:]); err != nil {
				return
			}
			body := make([]byte, binary.LittleEndian.Uint32(header[:]))
			if _, err := io.ReadFull(childIn, body); err != nil {
				return
			}
			result := guest.Result{OK: true, Version: 2, Status: 2}
			if body[0] == 2 {
				result.Rows = [][]*guest.Cell{{identityCell("42"), identityCell("12.3.3")}}
			}
			if err := writeReply(binary.LittleEndian.Uint32(body[1:]), result); err != nil {
				return
			}
		}
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	p, err := guest.Connect(ctx, in, out, completed, nil, io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	defer p.Abort(errors.New("test cleanup"))
	server, client := net.Pipe()
	defer server.Close()
	defer client.Close()
	client.SetDeadline(time.Now().Add(5 * time.Second))
	served := make(chan error, 1)
	go func() {
		defer server.Close()
		served <- Serve(server, p, 0, time.Minute, func() bool { return false }, Activity{
			Begin: func() bool { return true }, Idle: func(uint16) {}, Cleanup: func() {},
		})
	}()
	readPacket := func() []byte {
		t.Helper()
		var header [4]byte
		if _, err := io.ReadFull(client, header[:]); err != nil {
			t.Fatal(err)
		}
		body := make([]byte, int(header[0])|int(header[1])<<8|int(header[2])<<16)
		if _, err := io.ReadFull(client, body); err != nil {
			t.Fatal(err)
		}
		return body
	}
	writePacket := func(sequence byte, body []byte) {
		t.Helper()
		n := len(body)
		frame := append([]byte{byte(n), byte(n >> 8), byte(n >> 16), sequence}, body...)
		if _, err := client.Write(frame); err != nil {
			t.Fatal(err)
		}
	}
	readPacket() // greeting
	auth := make([]byte, 32)
	binary.LittleEndian.PutUint32(auth, 512) // CLIENT_PROTOCOL_41
	writePacket(1, append(auth, []byte("root\x00\x00")...))
	if body := readPacket(); body[0] != 0 {
		t.Fatal("handshake", body)
	}
	writePacket(0, []byte{14})
	if body := readPacket(); body[0] != 0 {
		t.Fatal("healthy PING", body)
	}
	want := errors.New("injected original worker trap")
	p.Abort(want)
	writePacket(0, []byte{14})
	body := readPacket()
	if len(body) < 9 || body[0] != 255 || binary.LittleEndian.Uint16(body[1:]) != 2013 || string(body[4:9]) != "HY000" || !strings.Contains(string(body[9:]), want.Error()) || strings.Contains(string(body), "timed out") {
		t.Fatalf("failed PING lost fatal cause: %q", body)
	}
	select {
	case err := <-served:
		if !errors.Is(err, want) {
			t.Fatal(err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("failed wire session did not close promptly")
	}
}
