package control

import (
	"context"
	"encoding/json"
	"io"
	"sync"
	"testing"
	"time"
)

func TestRequestCancellationDoesNotSerializeOtherOperations(t *testing.T) {
	in, writer := io.Pipe()
	reader, out := io.Pipe()
	entered := make(chan struct{})
	done := make(chan error, 1)
	operation := func(ctx context.Context, r Request) (map[string]any, error) {
		if r.Op == "held" {
			close(entered)
			<-ctx.Done()
			return nil, ctx.Err()
		}
		return map[string]any{"value": r.Op}, nil
	}
	go func() { done <- runWith(context.Background(), in, out, newManager(), operation); out.Close() }()
	enc := json.NewEncoder(writer)
	dec := json.NewDecoder(reader)
	var hello map[string]any
	if e := dec.Decode(&hello); e != nil {
		t.Fatal(e)
	}
	enc.Encode(Request{ID: 1, Op: "held"})
	<-entered
	enc.Encode(Request{ID: 2, Op: "fast"})
	var value map[string]any
	if e := dec.Decode(&value); e != nil {
		t.Fatal(e)
	}
	if value["id"] != float64(2) || value["value"] != "fast" {
		t.Fatal(value)
	}
	enc.Encode(Request{Op: "cancel", Target: 1})
	if e := dec.Decode(&value); e != nil {
		t.Fatal(e)
	}
	if value["id"] != float64(1) || value["ok"] != false || value["error"].(map[string]any)["code"] != "timeout" {
		t.Fatal(value)
	}
	enc.Encode(Request{ID: 3, Op: "shutdown"})
	if e := dec.Decode(&value); e != nil {
		t.Fatal(e)
	}
	if value["ok"] != true {
		t.Fatal(value)
	}
	select {
	case e := <-done:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("host not stopped")
	}
	writer.Close()
	reader.Close()
}
func TestOwnerEOFCancelsPendingAndCleansUp(t *testing.T) {
	in, writer := io.Pipe()
	reader, out := io.Pipe()
	entered := make(chan struct{})
	cancelled := make(chan struct{})
	done := make(chan error, 1)
	var once sync.Once
	operation := func(ctx context.Context, r Request) (map[string]any, error) {
		once.Do(func() { close(entered) })
		<-ctx.Done()
		close(cancelled)
		return nil, ctx.Err()
	}
	go func() { done <- runWith(context.Background(), in, out, newManager(), operation); out.Close() }()
	dec := json.NewDecoder(reader)
	var value map[string]any
	dec.Decode(&value)
	json.NewEncoder(writer).Encode(Request{ID: 1, Op: "held"})
	<-entered
	writer.Close()
	dec.Decode(&value)
	select {
	case <-cancelled:
	case <-time.After(5 * time.Second):
		t.Fatal("pending not cancelled")
	}
	select {
	case e := <-done:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("cleanup not completed")
	}
	reader.Close()
}
