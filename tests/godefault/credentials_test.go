//go:build integration

package godefault

import (
	"context"
	"database/sql"
	"encoding/binary"
	"io"
	"net"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func TestDefaultTestCredentials(t *testing.T) {
	t.Setenv("MARIAMEM_NATIVE_DIR", "")
	t.Setenv("MARIAMEM_RUNTIME", "")
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		if err := db.Close(); err != nil {
			t.Error(err)
		}
	}()
	if info := db.ConnectionInfo(); info.User != "root" || info.Password != "" {
		t.Fatalf("default credentials changed: user=%q", info.User)
	}
	for _, credentials := range []struct{ name, user, password string }{
		{"default", "root", ""},
		{"test_test", "test", "test"},
		{"root_root", "root", "root"},
		{"test_empty", "test", ""},
		{"arbitrary", "application", "synthetic-test-secret"},
		{"default_after_other_users", "root", ""},
	} {
		t.Run(credentials.name, func(t *testing.T) {
			cfg, err := mysql.ParseDSN(db.DSN())
			if err != nil {
				t.Fatal(err)
			}
			cfg.User, cfg.Passwd = credentials.user, credentials.password
			pool, err := sql.Open("mysql", cfg.FormatDSN())
			if err != nil {
				t.Fatal(err)
			}
			defer pool.Close()
			var got int
			if err := pool.QueryRowContext(ctx, "SELECT 1").Scan(&got); err != nil || got != 1 {
				t.Fatalf("query: got=%d error=%v", got, err)
			}
			for _, query := range []string{
				"CREATE TEMPORARY TABLE credential_probe(id INT PRIMARY KEY)",
				"INSERT INTO credential_probe VALUES(42)",
			} {
				if _, err := pool.ExecContext(ctx, query); err != nil {
					t.Fatal(err)
				}
			}
			if err := pool.QueryRowContext(ctx, "SELECT id FROM credential_probe").Scan(&got); err != nil || got != 42 {
				t.Fatalf("CRUD: got=%d error=%v", got, err)
			}
		})
	}
	// Credential bypass must still parse the handshake and reject invalid framing
	// or capabilities. Exercise both supported password response encodings.
	for _, tc := range []struct {
		name   string
		flags  uint32
		suffix []byte
		want   uint16 // 0=OK, 1=connection closes, otherwise MySQL error number
	}{
		{"secure_response", 512 | 32768, []byte("application\x00\x03abc"), 0},
		{"legacy_response", 512, []byte("application\x00synthetic\x00"), 0},
		{"empty_username", 512, []byte("\x00synthetic\x00"), 0},
		{"short_handshake", 512, nil, 1045},
		{"missing_username_terminator", 512, []byte("application"), 1},
		{"missing_legacy_response_terminator", 512, []byte("application\x00synthetic"), 1},
		{"missing_secure_response_length", 512 | 32768, []byte("application\x00"), 1},
		{"truncated_secure_response", 512 | 32768, []byte("application\x00\x05abc"), 1},
		{"missing_protocol41", 0, []byte("application\x00\x00"), 1235},
		{"unsupported_tls", 512 | 2048, []byte("application\x00\x00"), 1235},
	} {
		t.Run(tc.name, func(t *testing.T) {
			cfg, err := mysql.ParseDSN(db.DSN())
			if err != nil {
				t.Fatal(err)
			}
			conn, err := net.DialTimeout("tcp", cfg.Addr, 5*time.Second)
			if err != nil {
				t.Fatal(err)
			}
			defer conn.Close()
			if err := conn.SetDeadline(time.Now().Add(5 * time.Second)); err != nil {
				t.Fatal(err)
			}
			read := func() ([]byte, error) {
				var header [4]byte
				if _, err := io.ReadFull(conn, header[:]); err != nil {
					return nil, err
				}
				body := make([]byte, int(header[0])|int(header[1])<<8|int(header[2])<<16)
				_, err := io.ReadFull(conn, body)
				return body, err
			}
			if _, err := read(); err != nil {
				t.Fatal(err)
			}
			auth := make([]byte, 32)
			binary.LittleEndian.PutUint32(auth, tc.flags)
			auth = append(auth, tc.suffix...)
			frame := append([]byte{byte(len(auth)), byte(len(auth) >> 8), byte(len(auth) >> 16), 1}, auth...)
			if _, err := conn.Write(frame); err != nil {
				t.Fatal(err)
			}
			reply, err := read()
			if tc.want == 1 {
				if err != io.EOF {
					t.Fatalf("expected handshake close, got reply=%x error=%v", reply, err)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if tc.want == 0 {
				if len(reply) == 0 || reply[0] != 0 {
					t.Fatalf("expected OK, got %x", reply)
				}
			} else if len(reply) < 3 || reply[0] != 255 || binary.LittleEndian.Uint16(reply[1:3]) != tc.want {
				t.Fatalf("expected error %d, got %x", tc.want, reply)
			}
		})
	}
}
