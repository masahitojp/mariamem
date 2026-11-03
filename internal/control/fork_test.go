package control

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"testing"

	"github.com/masahitojp/mariamem/internal/forklimit"
)

func TestForkReservationsStayBoundToParentAndActiveLease(t *testing.T) {
	m := newManager()
	p, _ := forklimit.New(1)
	b := &baseline{limit: p}
	m.snaps[1] = b
	ctx := context.Background()
	first, err := m.call(ctx, Request{Op: "fork_reserve", Handle: 1})
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(first["reservation"])
	full, err := m.call(ctx, Request{Op: "fork_reserve", Handle: 1})
	if err != nil || full["full"] != true {
		t.Fatalf("full: %v %v", full, err)
	}
	if _, err := m.call(ctx, Request{Op: "fork_cancel", Handle: 2, Reservation: raw}); err == nil {
		t.Fatal("wrong parent canceled reservation")
	}
	a, err := m.claim(Request{Handle: 1, Reservation: raw}, false)
	if err != nil {
		t.Fatal(err)
	}
	if err := a.lease.Activate(); err != nil {
		t.Fatal(err)
	}
	if _, err := m.claim(Request{Handle: 1, Reservation: raw}, false); err == nil {
		t.Fatal("duplicate claim")
	}
	if _, err := m.call(ctx, Request{Op: "fork_cancel", Handle: 1, Reservation: raw}); err != nil {
		t.Fatal(err)
	}
	if _, err := p.TryAcquire(false); !errors.Is(err, forklimit.ErrFull) {
		t.Fatalf("active slot released: %v", err)
	}
	a.lease.Settle(nil)
	next, err := m.call(ctx, Request{Op: "fork_reserve", Handle: 1})
	if err != nil || next["full"] != false {
		t.Fatalf("reuse: %v %v", next, err)
	}
	p.Close()
	m.cancelReservations(b)
	if len(m.reservations) != 0 {
		t.Fatal("unused reservations survived Close")
	}
	if _, err := p.TryAcquire(false); !errors.Is(err, forklimit.ErrClosed) {
		t.Fatal(err)
	}
}

func TestOutOfRangeControlFieldsDoNotKillSharedHost(t *testing.T) {
	in, writer := io.Pipe()
	reader, out := io.Pipe()
	defer writer.Close()
	defer reader.Close()
	m := newManager()
	p, _ := forklimit.New(1)
	m.snaps[1] = &baseline{limit: p}
	done := make(chan error, 1)
	go func() { done <- runWith(context.Background(), in, out, m, m.call); out.Close() }()
	enc, dec := json.NewEncoder(writer), json.NewDecoder(reader)
	var reply map[string]any
	if err := dec.Decode(&reply); err != nil {
		t.Fatal(err)
	}
	for i, fields := range []map[string]any{
		{"op": "snapshot", "max_forks": json.Number("1267650600228229401496703205376")},
		{"op": "snapshot", "max_forks": true},
		{"op": "fork", "fork_timeout": "2147483648s"},
		{"op": "fork", "fork_timeout": json.Number("1267650600228229401496703205376")},
	} {
		fields["id"] = i + 1
		fields["handle"] = 1
		if err := enc.Encode(fields); err != nil {
			t.Fatal(err)
		}
		if err := dec.Decode(&reply); err != nil {
			t.Fatal(err)
		}
		if reply["ok"] != false || reply["closed"] != false || reply["error"].(map[string]any)["code"] != "invalid_options" {
			t.Fatalf("request-local error: %v", reply)
		}
	}
	if err := enc.Encode(Request{ID: 10, Op: "fork_reserve", Handle: 1}); err != nil {
		t.Fatal(err)
	}
	if err := dec.Decode(&reply); err != nil {
		t.Fatal(err)
	}
	if reply["ok"] != true || reply["full"] != false {
		t.Fatalf("host did not survive: %v", reply)
	}
	// This controlled baseline has no actual backing; dispose its unused lease
	// and registry before requesting the normal idle-only host shutdown.
	p.Close()
	m.cancelReservations(m.snaps[1])
	m.mu.Lock()
	delete(m.snaps, 1)
	m.mu.Unlock()
	if err := enc.Encode(Request{ID: 11, Op: "shutdown"}); err != nil {
		t.Fatal(err)
	}
	if err := dec.Decode(&reply); err != nil {
		t.Fatal(err)
	}
	if err := <-done; err != nil {
		t.Fatal(err)
	}
}
