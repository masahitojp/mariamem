package guest

import (
	"context"
	"encoding/binary"
	"errors"
	"io"
	"os"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/disposal"
)

func TestFailedGreetingRetainsLateJoinedOwnerWithNilProcess(t *testing.T) {
	childIn, in := io.Pipe()
	out, childOut := io.Pipe()
	completed := make(chan error, 1)
	defer childIn.Close()
	defer childOut.Close()
	defer func() {
		select {
		case completed <- nil:
		default:
		}
	}()
	go func() { _, _ = childOut.Write([]byte{0, 0, 0, 0}) }()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	p, err := connectWithFailure(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, io.Discard, nil, time.Millisecond)
	if p != nil {
		t.Fatal("failed startup became a usable Process")
	}
	var detail *diagnostic.Error
	if !errors.As(err, &detail) || detail.Code != "guest_connection" || detail.Stage != "guest_ready" || !strings.Contains(err.Error(), "invalid guest frame") {
		t.Fatal("lost original diagnostics", err)
	}
	owners := disposal.Owners(err)
	if len(owners) != 1 || owners[0].Complete() {
		t.Fatal("lost unjoined Process", err)
	}
	probe, stop := context.WithCancel(context.Background())
	stop()
	if e := disposal.Retry(probe, err); !errors.Is(e, context.Canceled) {
		t.Fatal(e)
	}
	completed <- nil
	if e := disposal.Retry(ctx, err); e != nil {
		t.Fatal(e)
	}
	if !owners[0].Complete() || !strings.Contains(err.Error(), "invalid guest frame") {
		t.Fatal("rewrote failed startup")
	}
}

type heldEOF struct {
	*os.File
	reached chan struct{}
	release chan struct{}
}

func (r *heldEOF) Read(b []byte) (int, error) {
	n, err := r.File.Read(b)
	if err == io.EOF {
		close(r.reached)
		<-r.release
	}
	return n, err
}

func TestStoppedJoinsReaderAndClosesAllPipeEndpoints(t *testing.T) {
	childIn, in, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	out, childOut, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { childIn.Close(); in.Close(); out.Close(); childOut.Close() })
	completed, stopped := make(chan error, 1), make(chan error, 1)
	held := &heldEOF{File: out, reached: make(chan struct{}), release: make(chan struct{})}
	go func() {
		body := []byte(`{"request_id":0,"result":{"ready":true,"api_version":2,"max_sessions":16}}`)
		binary.Write(childOut, binary.LittleEndian, uint32(len(body)))
		childOut.Write(body)
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	var peerCloses atomic.Int32
	p, err := ConnectWithStopped(ctx, in, held, completed, func() { peerCloses.Add(1); childIn.Close(); childOut.Close() }, io.Discard, nil, stopped)
	if err != nil {
		t.Fatal(err)
	}
	stopped <- nil
	select {
	case <-held.reached:
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	short, stopCancel := context.WithTimeout(ctx, 20*time.Millisecond)
	if err := p.WaitStopped(short); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatal("reader not joined", err)
	}
	stopCancel()
	close(held.release)
	if err := p.WaitStopped(ctx); err != nil {
		t.Fatal(err)
	}
	for _, f := range []*os.File{childIn, in, out, childOut} {
		if _, err := f.Stat(); !errors.Is(err, os.ErrClosed) {
			t.Fatal("pipe endpoint still open", f.Name(), err)
		}
	}
	select {
	case <-p.Done():
		t.Fatal("cleanup completion published early")
	default:
	}
	completed <- nil
	select {
	case <-p.Done():
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	p.Abort(errors.New("duplicate abort"))
	if peerCloses.Load() != 1 {
		t.Fatal("duplicate peer close")
	}
}
