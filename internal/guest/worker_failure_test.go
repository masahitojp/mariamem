package guest

import (
	"context"
	"encoding/binary"
	"errors"
	"io"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

func TestWorkerTrapFailsPendingCallsBeforeCompletion(t *testing.T) {
	childIn, in := io.Pipe()
	out, childOut := io.Pipe()
	completed := make(chan error, 1)
	failed := make(chan error, 1)
	trigger := make(chan struct{})
	releaseOwner := make(chan struct{})
	want := errors.New("injected WASIX worker trap")
	pool := &base.ThreadPool{}
	pool.NotifyWorkerFailure(func(cause any) { failed <- cause.(error) })
	m := &base.Module{Threads: pool}
	defer childIn.Close()
	defer childOut.Close()
	var release sync.Once
	defer release.Do(func() { close(releaseOwner) })
	go func() {
		body := []byte(`{"request_id":0,"result":{"ready":true,"api_version":2,"max_sessions":16}}`)
		frame := make([]byte, 4+len(body))
		binary.LittleEndian.PutUint32(frame, uint32(len(body)))
		copy(frame[4:], body)
		if _, err := childOut.Write(frame); err != nil {
			completed <- err
			return
		}
		// Consume two requests so both sessions are pending when the worker dies.
		for i := 0; i < 2; i++ {
			var head [4]byte
			if _, err := io.ReadFull(childIn, head[:]); err != nil {
				completed <- err
				return
			}
			if _, err := io.CopyN(io.Discard, childIn, int64(binary.LittleEndian.Uint32(head[:]))); err != nil {
				completed <- err
				return
			}
		}
		ownerEntered := make(chan struct{})
		base.ThreadLaunch(m, func(*base.Module, int32) { close(ownerEntered); <-releaseOwner })
		<-ownerEntered
		base.ThreadLaunch(m, func(*base.Module, int32) { <-trigger; panic(want) })
		close(trigger)
		cause := pool.WaitThreads()
		completed <- cause.(error)
	}()
	// A long request deadline makes a timeout-based implementation fail the
	// short observation bound. Completion is held independently by releaseOwner.
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	p, err := ConnectWithFailure(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, io.Discard, failed)
	if err != nil {
		t.Fatal(err)
	}
	responses := make(chan error, 2)
	for slot := uint32(0); slot < 2; slot++ {
		go func() { _, err := p.Call(ctx, 2, slot, []byte("SELECT 1")); responses <- err }()
	}
	for i := 0; i < 2; i++ {
		select {
		case err := <-responses:
			if !errors.Is(err, want) || errors.Is(err, context.DeadlineExceeded) {
				t.Fatal("lost trap or waited for timeout", err)
			}
		case <-time.After(3 * time.Second):
			t.Fatal("pending request waited for timeout or join")
		}
	}
	if !errors.Is(p.Err(), want) {
		t.Fatal("instance did not retain original failure", p.Err())
	}
	if _, err := p.Call(ctx, 2, 2, []byte("SELECT 2")); !errors.Is(err, want) {
		t.Fatal("failed instance admitted another call", err)
	}
	select {
	case <-p.Done():
		t.Fatal("completion signalled before the remaining owner joined")
	default:
	}
	release.Do(func() { close(releaseOwner) })
	select {
	case <-p.Done():
	case <-time.After(3 * time.Second):
		t.Fatal("cleanup did not complete after owner exit")
	}
}
