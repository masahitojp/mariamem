package mariamem

import (
	"context"
	"errors"
	"net"
	"strconv"
	"testing"
)

func TestDialContextPreconditions(t *testing.T) {
	db := &Database{server: &fakeBackend{}, info: ConnectionInfo{Host: "127.0.0.1", Port: 12345}}
	addr := net.JoinHostPort(db.info.Host, strconv.Itoa(db.info.Port))
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if c, e := db.DialContext(ctx, "tcp", addr); c != nil || !errors.Is(e, context.Canceled) {
		t.Fatal(c, e)
	}
	for _, input := range [][2]string{{"unix", addr}, {"tcp", "127.0.0.1:1"}} {
		if c, e := db.DialContext(context.Background(), input[0], input[1]); c != nil || e == nil {
			t.Fatal(c, e)
		}
	}
	for _, network := range []string{"tcp", "tcp4"} {
		_, e := db.DialContext(context.Background(), network, addr)
		var he *HostError
		if !errors.As(e, &he) || he.Code != "dial" {
			t.Fatal(e)
		}
	}
	db.closed = true
	if _, e := db.DialContext(context.Background(), "tcp", addr); !errors.Is(e, ErrClosed) {
		t.Fatal(e)
	}
	db.closed = false
	db.failure = hostError(errors.New("latched"), "unusable", true)
	if _, e := db.DialContext(context.Background(), "tcp", addr); !errors.Is(e, ErrUnusable) {
		t.Fatal(e)
	}
	if !errors.Is(hostError(errors.New("full"), "capacity", false), ErrCapacity) {
		t.Fatal("capacity classification lost")
	}
}
