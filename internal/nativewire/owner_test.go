package nativewire

import (
	"errors"
	"math"
	"sync"
	"sync/atomic"
	"testing"
)

func lease(t *testing.T, o *Owner) *Lease {
	t.Helper()
	l, e := o.ReserveLocked()
	if e != nil {
		t.Fatal(e)
	}
	return l
}
func opened(t *testing.T, o *Owner, l *Lease) {
	t.Helper()
	if e := o.BeginOpenLocked(l); e != nil {
		t.Fatal(e)
	}
	if e := o.OpenedLocked(l, l.Token()); e != nil {
		t.Fatal(e)
	}
}
func TestCapacityRequiresNativeAndBothRelays(t *testing.T) {
	for _, nativeFirst := range []bool{false, true} {
		for _, firstPart := range []uint8{Reader, Writer} {
			secondPart := uint8(Reader|Writer) ^ firstPart
			o := New(7)

			var first *Lease
			for i := 0; i < Capacity; i++ {
				l := lease(t, o)
				opened(t, o, l)
				if i == 0 {
					first = l
				}
			}
			if _, e := o.ReserveLocked(); !errors.Is(e, ErrCapacity) {
				t.Fatal(e)
			}
			if nativeFirst {
				if done, e := o.NativeRetiredLocked(first); done || e != nil {
					t.Fatal(done, e)
				}
			}
			if done, e := o.RelayDoneLocked(first, firstPart); done || e != nil {
				t.Fatal(done, e)
			}
			if !nativeFirst {
				if done, e := o.RelayDoneLocked(first, secondPart); done || e != nil {
					t.Fatal(done, e)
				}
			}
			if _, e := o.ReserveLocked(); !errors.Is(e, ErrCapacity) {
				t.Fatal("early reuse", e)
			}
			var done bool
			var e error
			if nativeFirst {
				done, e = o.RelayDoneLocked(first, secondPart)
			} else {
				done, e = o.NativeRetiredLocked(first)
			}
			if !done || e != nil {
				t.Fatal(done, e)
			}
			replacement := lease(t, o)
			if replacement.token.Slot != first.token.Slot || replacement.token.Generation <= first.token.Generation {
				t.Fatal("identity reuse")
			}
			if !o.StaleLocked(first.token) {
				t.Fatal("old token accepted")
			}
			if _, e = o.NativeRetiredLocked(first); e == nil {
				t.Fatal("old retirement accepted")
			}
			if o.CountLocked() != Capacity {
				t.Fatal("capacity changed")
			}

		}

	}
}

func TestUncertainOpenRetainsLeaseUntilDisposal(t *testing.T) {
	o := New(1)
	l := lease(t, o)
	o.BeginOpenLocked(l)
	o.UncertainLocked(l)
	if _, e := o.ReserveLocked(); !errors.Is(e, ErrClosed) {
		t.Fatal(e)
	}
	o.RelayDoneLocked(l, Reader)
	o.RelayDoneLocked(l, Writer)
	o.NativeRetiredLocked(l)
	if o.CountLocked() != 1 {
		t.Fatal("uncertainty forgiven")
	}
	o.DisposeLocked()
	if o.CountLocked() != 0 {
		t.Fatal("not disposed")
	}
	if _, e := o.ReserveLocked(); !errors.Is(e, ErrClosed) {
		t.Fatal(e)
	}
}
func TestCaptureCannotOvertakeOpen(t *testing.T) {
	o := New(1)
	l := lease(t, o)
	if !errors.Is(o.BeginCaptureLocked(), ErrBusy) {
		t.Fatal("reserved capture")
	}
	o.BeginOpenLocked(l)
	if !errors.Is(o.BeginCaptureLocked(), ErrBusy) {
		t.Fatal("opening capture")
	}
	o.OpenedLocked(l, l.token)
	if e := o.BeginCaptureLocked(); e != nil {
		t.Fatal(e)
	}
	if _, e := o.ReserveLocked(); !errors.Is(e, ErrClosed) {
		t.Fatal(e)
	}
	o.EndCaptureLocked()
	if _, e := o.ReserveLocked(); e != nil {
		t.Fatal(e)
	}
}
func TestDefinitiveCancellationAndRejection(t *testing.T) {
	o := New(1)
	for _, sent := range []bool{false, true} {
		l := lease(t, o)
		if sent {
			o.BeginOpenLocked(l)
			if e := o.RejectLocked(l, l.token); e != nil {
				t.Fatal(e)
			}
		} else {
			if e := o.CancelReservedLocked(l); e != nil {
				t.Fatal(e)
			}
		}
		o.RelayDoneLocked(l, Reader)
		if o.CountLocked() != 1 {
			t.Fatal("reader is not writer join")
		}
		done, e := o.RelayDoneLocked(l, Writer)
		if !done || e != nil {
			t.Fatal(done, e)
		}
	}
}
func TestWrongIdentityCannotInstallAndCountersDoNotWrap(t *testing.T) {
	o := New(1)
	l := lease(t, o)
	o.BeginOpenLocked(l)
	bad := l.token
	bad.Generation++
	if !errors.Is(o.OpenedLocked(l, bad), ErrIdentity) {
		t.Fatal("wrong identity")
	}
	o.OpenedLocked(l, l.token)
	var a atomic.Uint32
	var b atomic.Uint64
	a.Store(math.MaxUint32 - 1)
	b.Store(math.MaxUint64 - 1)
	if n, e := Next32(&a); n != math.MaxUint32 || e != nil {
		t.Fatal(n, e)
	}
	if n, e := Next64(&b); n != math.MaxUint64 || e != nil {
		t.Fatal(n, e)
	}
	for i := 0; i < 3; i++ {
		if _, e := Next32(&a); !errors.Is(e, ErrExhausted) {
			t.Fatal(e)
		}
		if _, e := Next64(&b); !errors.Is(e, ErrExhausted) {
			t.Fatal(e)
		}
	}
	other := New(2)
	other.generations[0] = math.MaxUint64
	for i := 0; i < 3; i++ {
		if _, e := other.ReserveLocked(); e == nil {
			t.Fatal("generation wrapped")
		}
	}
}
func TestConcurrentIdentityAllocation(t *testing.T) {
	var c atomic.Uint64
	var wg sync.WaitGroup
	out := make(chan uint64, 128)
	for i := 0; i < 128; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			n, e := Next64(&c)
			if e != nil {
				t.Error(e)
			}
			out <- n
		}()
	}
	wg.Wait()
	close(out)
	seen := map[uint64]bool{}
	for n := range out {
		if n == 0 || seen[n] {
			t.Fatal("duplicate", n)
		}
		seen[n] = true
	}
}
