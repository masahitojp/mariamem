package host

import (
	"context"
	"encoding/binary"
	"errors"
	"io"
	"net"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/nativewire"
)

func TestRejectCapacityWritesMySQL1040AndCloses(t *testing.T) {
	client, server := net.Pipe()
	defer client.Close()
	done := make(chan struct{})
	go func() {
		defer close(done)
		RejectCapacity(server)
	}()
	_ = client.SetReadDeadline(time.Now().Add(2 * time.Second))
	var hdr [4]byte
	if _, err := io.ReadFull(client, hdr[:]); err != nil {
		t.Fatal(err)
	}
	n := int(hdr[0]) | int(hdr[1])<<8 | int(hdr[2])<<16
	body := make([]byte, n)
	if _, err := io.ReadFull(client, body); err != nil {
		t.Fatal(err)
	}
	if len(body) < 9 || body[0] != 0xff {
		t.Fatalf("unexpected packet: %x", body)
	}
	errno := binary.LittleEndian.Uint16(body[1:3])
	if errno != 1040 || string(body[3:9]) != "#08004" {
		t.Fatalf("got errno=%d state=%q want 1040/#08004", errno, string(body[3:9]))
	}
	var one [1]byte
	if _, err := client.Read(one[:]); !errors.Is(err, io.EOF) {
		t.Fatalf("expected EOF after RejectCapacity, got %v", err)
	}
	<-done
}

func TestNativeRejectionMapping(t *testing.T) {
	cases := []struct {
		in   error
		want string
	}{
		{nativewire.ErrCapacity, "capacity"},
		{nativewire.ErrBusy, "busy"},
		{nativewire.ErrClosed, "closed"},
		{&nativewire.Rejected{Code: "transaction_active", Message: "tx open"}, "transaction_active"},
	}
	for _, tc := range cases {
		err := nativeRejection(tc.in)
		var rej *Rejected
		if !errors.As(err, &rej) || rej.Code != tc.want {
			t.Fatalf("nativeRejection(%v) = %v (want code %q)", tc.in, err, tc.want)
		}
	}
	if nativeRejection(nil) != nil {
		t.Fatal("nil error mapped to non-nil")
	}
	plain := errors.New("other")
	if nativeRejection(plain) != plain {
		t.Fatal("plain error unexpectedly wrapped")
	}
}

func TestStartNativeCanceledContext(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	s, err := startNative(ctx, nil, time.Second, nil, "fake", func(nativewire.Execution) <-chan error {
		t.Fatal("runner must not start on canceled context")
		return nil
	}, func() (net.Listener, error) {
		t.Fatal("listener must not open on canceled context")
		return nil, nil
	})
	if s != nil || !errors.Is(err, context.Canceled) {
		t.Fatalf("got s=%v err=%v", s, err)
	}
}
