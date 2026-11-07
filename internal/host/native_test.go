package host

import (
	"context"
	"errors"
	"io"
	"net"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/nativewire"
	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/snapshot"
)

func TestNativeServiceErrorMapping(t *testing.T) {
	for _, v := range []struct {
		input error
		code  string
	}{{nativewire.ErrCapacity, "capacity"}, {nativewire.ErrBusy, "busy"}, {nativewire.ErrClosed, "closed"}, {&nativewire.Rejected{Code: "transaction_active", Message: "transaction"}, "transaction_active"}} {
		err := nativeRejection(v.input)
		var reject *Rejected
		if !errors.As(err, &reject) || reject.Code != v.code || !errors.Is(err, v.input) {
			t.Fatalf("mapping: %v", err)
		}
	}
}
func TestNativeStartupRetainsBorrowedBaseline(t *testing.T) {
	source := prepared.NewRootSource(true)
	capture := &prepared.Capture{}
	if e := capture.BindRootSource(source, "fake"); e != nil {
		t.Fatal(e)
	}
	capture.Request()
	if e := capture.CompleteRoot(source, "fake", []string{"."}, nil); e != nil {
		t.Fatal(e)
	}
	root, e := capture.TakeRoot("fake")
	if e != nil {
		t.Fatal(e)
	}
	owned, e := snapshot.OwnRoot(root, "fake")
	if e != nil {
		t.Fatal(e)
	}
	entered := make(chan struct{})
	release := make(chan struct{})
	ctx, cancel := context.WithCancel(context.Background())
	result := make(chan error, 1)
	runner := func(x nativewire.Execution) <-chan error {
		close(entered)
		done := make(chan error, 1)
		go func() { _, _ = io.Copy(io.Discard, x.Input); <-release; done <- nil }()
		return done
	}
	go func() {
		_, e := startNative(ctx, owned, time.Second, io.Discard, "fake", runner, func() (net.Listener, error) {
			t.Error("canceled startup listened")
			return nil, errors.New("unexpected")
		})
		result <- e
	}()
	<-entered
	cancel()
	err := <-result
	if !errors.Is(err, context.Canceled) || len(disposal.Owners(err)) != 1 {
		t.Fatalf("startup ownership lost: %v", err)
	}
	closed := make(chan error, 1)
	go func() { closed <- owned.Close() }()
	select {
	case e := <-closed:
		t.Fatalf("baseline released before runtime join: %v", e)
	default:
	}
	close(release)
	if e := disposal.Retry(context.Background(), err); e != nil {
		t.Fatal(e)
	}
	select {
	case e := <-closed:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(time.Second):
		t.Fatal("late borrowed baseline not released")
	}
}
