package guest

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"testing"
	"testing/synctest"
)

// Pause only a large response body. Closing the host reader must unblock
// both the paused Read and the guest's Write, just as an aborted link does.
type pausedBodyReader struct {
	byteReader
	resume <-chan struct{}
	closed chan struct{}
}

func (r *pausedBodyReader) Read(dst []byte) (int, error) {
	if len(dst) > len(r.p.buf) {
		select {
		case <-r.resume:
		case <-r.closed:
			return 0, io.ErrClosedPipe
		}
	}
	return r.byteReader.Read(dst)
}
func (r *pausedBodyReader) Close() error {
	close(r.closed)
	return r.byteReader.Close()
}

func TestFullLinkedStreamLifecycle(t *testing.T) {
	for _, direction := range []string{"request", "response"} {
		for _, event := range []string{"cancel", "disconnect", "drain"} {
			t.Run(direction+"/"+event, func(t *testing.T) {
				synctest.Test(t, func(t *testing.T) { testFullLinkedStream(t, direction, event) })
			})
		}
	}
}

func testFullLinkedStream(t *testing.T, direction, event string) {
	ctx := t.Context()
	childIn, in := newBytePipe()
	out, childOut := newBytePipe()
	resume := make(chan struct{})
	bodyReader := &pausedBodyReader{out, resume, make(chan struct{})}
	completed := make(chan error, 1)
	send := func(id uint32, result Result) error {
		msg := struct {
			ID     uint32 `json:"request_id"`
			Result Result `json:"result"`
		}{id, result}
		b, err := json.Marshal(msg)
		if err != nil {
			return err
		}
		if err := binary.Write(childOut, binary.LittleEndian, uint32(len(b))); err != nil {
			return err
		}
		_, err = childOut.Write(b)
		return err
	}
	if err := send(0, Result{Ready: true, Version: 2, MaxSessions: 1}); err != nil {
		t.Fatal(err)
	}
	p, err := Connect(ctx, in, bodyReader, completed, func() { childIn.Close(); childOut.Close() }, io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	payload := bytes.Repeat([]byte{'q'}, 3*len(in.p.buf))
	// The peer echoes the request as one large JSON result, then consumes
	// the stop frame. Publish completion only after its final I/O.
	peer := func() error {
		if direction == "request" {
			<-resume
		}
		var size uint32
		if err := binary.Read(childIn, binary.LittleEndian, &size); err != nil {
			return err
		}
		frame := make([]byte, size)
		if _, err := io.ReadFull(childIn, frame); err != nil {
			return err
		}
		if len(frame) < 9 || !bytes.Equal(frame[9:], payload) {
			return errors.New("corrupt request")
		}
		if err := send(binary.LittleEndian.Uint32(frame[1:]), Result{OK: true, RawRows: []string{string(frame[9:])}}); err != nil {
			return err
		}
		if err := binary.Read(childIn, binary.LittleEndian, &size); err != nil {
			return err
		}
		if size != 0 {
			return errors.New("missing stop frame")
		}
		return nil
	}
	go func() { completed <- peer() }()
	callCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	result := make(chan error, 1)
	go func() {
		r, err := p.Call(callCtx, 2, 0, payload)
		if err == nil && (!r.OK || len(r.RawRows) != 1 || r.RawRows[0] != string(payload)) {
			err = errors.New("corrupt response")
		}
		result <- err
	}()
	synctest.Wait()
	pipe := in.p
	if direction == "response" {
		pipe = out.p
	}
	if pipe.used != len(pipe.buf) {
		t.Fatalf("buffered %d, want %d", pipe.used, len(pipe.buf))
	}
	switch event {
	case "cancel":
		cancel()
		if err := <-result; !errors.Is(err, context.Canceled) {
			t.Fatalf("cancelled call: %v", err)
		}
	case "disconnect":
		reason := errors.New("client disconnected")
		p.Abort(reason)
		if err := <-result; err == nil || !errors.Is(p.Err(), reason) {
			t.Fatalf("call=%v cause=%v", err, p.Err())
		}
	}
	close(resume)
	if event == "drain" {
		if err := <-result; err != nil {
			t.Fatal(err)
		}
		if err := p.Shutdown(ctx); err != nil {
			t.Fatal(err)
		}
	}
	<-p.Done()
	if err := p.RetryDisposal(ctx); err != nil {
		t.Fatal(err)
	}
}
