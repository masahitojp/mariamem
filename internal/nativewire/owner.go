// Package nativewire owns host-side reservations for the experimental native
// endpoint. It parses no SQL or MySQL packets and does not select public routing.
package nativewire

import (
	"errors"
	"math"
	"sync/atomic"
)

var (
	ErrCapacity  = errors.New("native session capacity exhausted")
	ErrClosed    = errors.New("native owner is not accepting")
	ErrBusy      = errors.New("native OPEN is pending")
	ErrExhausted = errors.New("native identity exhausted")
	ErrIdentity  = errors.New("native session identity mismatch")
	ErrState     = errors.New("native session state mismatch")
)

const Capacity = 16
const (
	Reader = 1
	Writer = 2
)

type Token struct {
	Epoch      uint64
	Slot       uint32
	Generation uint64
}
type phase uint8

const (
	reserved phase = iota
	opening
	active
	retiring
	uncertain
)

type Lease struct {
	token  Token
	state  phase
	native bool
	relays uint8
}

func (l *Lease) Token() Token { return l.token }

// All Locked methods require the enclosing instance lifecycle lock. They never
// acquire another lock or wait for I/O, a worker or a relay.
type Owner struct {
	epoch                       uint64
	slots                       [Capacity]*Lease
	generations                 [Capacity]uint64
	closed, capturing, disposed bool
}

func New(epoch uint64) *Owner {
	if epoch == 0 {
		panic("zero native epoch")
	}
	return &Owner{epoch: epoch}
}
func (o *Owner) current(l *Lease) bool {
	return l != nil && l.token.Epoch == o.epoch && l.token.Slot < Capacity && o.slots[l.token.Slot] == l
}
func (o *Owner) CountLocked() (n int) {
	for _, l := range o.slots {
		if l != nil {
			n++
		}
	}
	return
}
func (o *Owner) ReserveLocked() (*Lease, error) {
	if o.closed || o.capturing || o.disposed {
		return nil, ErrClosed
	}
	for i, l := range o.slots {
		if l != nil {
			continue
		}
		if o.generations[i] == math.MaxUint64 {
			o.closed = true
			return nil, ErrExhausted
		}
		o.generations[i]++
		l = &Lease{token: Token{o.epoch, uint32(i), o.generations[i]}, state: reserved}
		o.slots[i] = l
		return l, nil
	}
	return nil, ErrCapacity
}
func (o *Owner) BeginOpenLocked(l *Lease) error {
	if !o.current(l) || l.state != reserved {
		return ErrState
	}
	if o.closed || o.capturing {
		return ErrClosed
	}
	l.state = opening
	return nil
}
func (o *Owner) OpenedLocked(l *Lease, t Token) error {
	if !o.current(l) || l.token != t {
		return ErrIdentity
	}
	if l.state != opening {
		return ErrState
	}
	l.state = active
	return nil
}
func (o *Owner) CancelReservedLocked(l *Lease) error {
	if !o.current(l) || l.state != reserved {
		return ErrState
	}
	l.native = true
	l.state = retiring
	return nil
}

// RejectLocked is only for the protocol's definitive no-worker rejection.
func (o *Owner) RejectLocked(l *Lease, t Token) error {
	if !o.current(l) || l.token != t || l.state != opening {
		return ErrIdentity
	}
	l.native = true
	l.state = retiring
	return nil
}
func (o *Owner) UncertainLocked(l *Lease) {
	o.closed = true
	if o.current(l) {
		l.state = uncertain
	}
}
func (o *Owner) release(l *Lease) bool {
	if l.native && l.relays == Reader|Writer && l.state != uncertain {
		o.slots[l.token.Slot] = nil
		return true
	}
	return false
}
func (o *Owner) NativeRetiredLocked(l *Lease) (bool, error) {
	if !o.current(l) {
		return false, ErrIdentity
	}
	if l.state != active && l.state != retiring && l.state != uncertain {
		return false, ErrState
	}
	l.native = true
	if l.state != uncertain {
		l.state = retiring
	}
	return o.release(l), nil
}
func (o *Owner) RelayDoneLocked(l *Lease, part uint8) (bool, error) {
	if !o.current(l) || (part != Reader && part != Writer) || l.relays&part != 0 {
		return false, ErrState
	}
	l.relays |= part
	return o.release(l), nil
}
func (o *Owner) StaleLocked(t Token) bool {
	if t.Epoch != o.epoch || t.Slot >= Capacity || t.Generation == 0 || t.Generation > o.generations[t.Slot] {
		return false
	}
	l := o.slots[t.Slot]
	return l == nil || l.token != t
}
func (o *Owner) BeginCaptureLocked() error {
	if o.closed || o.capturing || o.disposed {
		return ErrClosed
	}
	for _, l := range o.slots {
		if l != nil && (l.state == reserved || l.state == opening || l.state == uncertain) {
			return ErrBusy
		}
	}
	o.capturing = true
	return nil
}
func (o *Owner) EndCaptureLocked() { o.capturing = false }
func (o *Owner) StopLocked()       { o.closed = true }

// DisposeLocked is called only after root/native, shared reader and host joins.
func (o *Owner) DisposeLocked() {
	o.closed = true
	o.disposed = true
	for i := range o.slots {
		o.slots[i] = nil
	}
}

// Counters saturate: every call after exhaustion fails without wrapping to one.
func Next32(v *atomic.Uint32) (uint32, error) {
	for {
		n := v.Load()
		if n == math.MaxUint32 {
			return 0, ErrExhausted
		}
		if v.CompareAndSwap(n, n+1) {
			return n + 1, nil
		}
	}
}
func Next64(v *atomic.Uint64) (uint64, error) {
	for {
		n := v.Load()
		if n == math.MaxUint64 {
			return 0, ErrExhausted
		}
		if v.CompareAndSwap(n, n+1) {
			return n + 1, nil
		}
	}
}
