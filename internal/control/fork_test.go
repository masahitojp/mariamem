package control

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/forklimit"
	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/runtimekind"
	"github.com/masahitojp/mariamem/internal/snapshot"
)

func handoffBaseline(t *testing.T) *baseline {
	t.Helper()
	data := make([]byte, prepared.BlockSize)
	block, err := prepared.TakeBlock(data, len(data))
	if err != nil {
		t.Fatal(err)
	}
	f, err := prepared.NewHeapFile(int64(len(data)), []prepared.Block{block}, fmt.Sprintf("%x", sha256.Sum256(data)))
	if err != nil {
		t.Fatal(err)
	}
	h, err := prepared.NewHeap(runtimekind.GuestSHA256, []string{"."}, map[string]*prepared.HeapFile{"f": f})
	if err != nil {
		t.Fatal(err)
	}
	owned, err := snapshot.OwnHeap(h, runtimekind.GuestSHA256)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { owned.Close() })
	p, _ := forklimit.New(1)
	return &baseline{owned: owned, limit: p}
}

func TestHandoffAcknowledgementIsBoundIdempotentAndSurvivesParentClose(t *testing.T) {
	for _, closeParent := range []bool{false, true} {
		t.Run(fmt.Sprint(closeParent), func(t *testing.T) {
			m, ctx := newManager(), context.Background()
			b := handoffBaseline(t)
			m.snaps[1] = b
			reserved, err := m.call(ctx, Request{Op: "fork_reserve", Handle: 1})
			if err != nil {
				t.Fatal(err)
			}
			raw, _ := json.Marshal(reserved["reservation"])
			path := filepath.Join(t.TempDir(), "export")
			if _, err := m.call(ctx, Request{Op: "handoff", Handle: 1, Reservation: raw, TransferPath: path}); err != nil {
				t.Fatal(err)
			}
			if _, err := m.call(ctx, Request{Op: "handoff_release", Handle: 2, Reservation: raw}); err == nil {
				t.Fatal("wrong parent acknowledged lease")
			}
			if _, err := m.call(ctx, Request{Op: "fork_cancel", Handle: 1, Reservation: raw}); err != nil {
				t.Fatal(err)
			}
			if _, err := b.limit.TryAcquire(false); !errors.Is(err, forklimit.ErrFull) {
				t.Fatalf("export released early: %v", err)
			}
			if closeParent {
				if _, err := m.call(ctx, Request{Op: "snapshot_close", Handle: 1}); err != nil {
					t.Fatal(err)
				}
			}
			if _, err := m.call(ctx, Request{Op: "handoff_release", Handle: 1, Reservation: raw}); err != nil {
				t.Fatal(err)
			}
			if _, err := os.Stat(path); !errors.Is(err, os.ErrNotExist) {
				t.Fatalf("export not removed: %v", err)
			}
			var next *forklimit.Lease
			if !closeParent {
				next, err = b.limit.TryAcquire(false)
				if err != nil {
					t.Fatal(err)
				}
				defer next.Cancel()
			}
			if _, err := m.call(ctx, Request{Op: "handoff_release", Handle: 1, Reservation: raw}); err != nil {
				t.Fatal(err)
			}
			_, err = b.limit.TryAcquire(false)
			want := forklimit.ErrFull
			if closeParent {
				want = forklimit.ErrClosed
			}
			if !errors.Is(err, want) {
				t.Fatalf("duplicate acknowledgement affected another lease: %v", err)
			}
			if len(m.reservations) != 0 {
				t.Fatal("settled history retained")
			}
		})
	}
}

func TestHandoffExistingDestinationIsPreservedAndReservationReturned(t *testing.T) {
	m := newManager()
	b := handoffBaseline(t)
	m.snaps[1] = b
	reserved, err := m.call(context.Background(), Request{Op: "fork_reserve", Handle: 1})
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(reserved["reservation"])
	path := t.TempDir()
	marker := filepath.Join(path, "user-input")
	if err := os.WriteFile(marker, []byte("preserved"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := m.call(context.Background(), Request{Op: "handoff", Handle: 1, Reservation: raw, TransferPath: path}); err == nil {
		t.Fatal("existing destination overwritten")
	}
	if data, err := os.ReadFile(marker); err != nil || string(data) != "preserved" {
		t.Fatal(string(data), err)
	}
	l, err := b.limit.TryAcquire(false)
	if err != nil {
		t.Fatal("failed export retained unused slot", err)
	}
	l.Cancel()
	if len(m.reservations) != 0 {
		t.Fatal("failed export record retained")
	}
}

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

func TestCapacityReplyAndWaitErrorReportCapAndOccupiedSlots(t *testing.T) {
	m := newManager()
	b := handoffBaseline(t)
	m.snaps[1] = b
	defer b.forkLimit().Close()
	defer m.cancelReservations(b)
	if _, err := m.call(context.Background(), Request{Op: "fork_reserve", Handle: 1}); err != nil {
		t.Fatal(err)
	}
	reply, err := m.call(context.Background(), Request{Op: "fork_reserve", Handle: 1})
	if err != nil || reply["full"] != true || reply["max_forks"] != 1 || reply["occupied_slots"] != 1 {
		t.Fatal(reply, err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Millisecond)
	defer cancel()
	_, err = m.call(ctx, Request{Op: "fork", Handle: 1})
	var detail *diagnostic.Error
	if !errors.Is(err, context.DeadlineExceeded) || !errors.As(err, &detail) || detail.Code != "pool_timeout" || detail.Stage != "fork_wait" {
		t.Fatal(err)
	}
	if !strings.Contains(err.Error(), "max_forks=1, occupied_slots=1") || !strings.Contains(err.Error(), "close owned children or increase max_forks") {
		t.Fatal("control error lost capacity diagnostic", err)
	}
}
