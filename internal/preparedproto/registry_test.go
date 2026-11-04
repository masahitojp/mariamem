package preparedproto

import "testing"

func TestRegistrySessionsCapacityAndLifetime(t *testing.T) {
	if _, e := NewRegistry(0); e == nil {
		t.Fatal("zero generation")
	}
	a, _ := NewRegistry(1)
	b, _ := NewRegistry(2)
	aid, e := a.Add(1, 99, 65)
	if e != nil {
		t.Fatal(e)
	}
	bid, e := b.Add(2, 200, 0)
	if e != nil || aid != bid {
		t.Fatal("wire IDs are session-local", aid, bid, e)
	}
	ae, _ := a.Lookup(aid)
	be, _ := b.Lookup(bid)
	if ae.Handle == be.Handle || ae.Parameters != 65 {
		t.Fatal("ownership lost")
	}
	for h := uint32(100); h < 230; h++ {
		if _, e := a.Add(1, h, 0); e != nil {
			t.Fatal(e)
		}
	}
	for _, bad := range [][3]uint32{{2, 1, 0}, {1, 0, 0}, {1, 99, 0}, {1, 1, 65536}} {
		if _, e := a.Add(bad[0], bad[1], bad[2]); e == nil {
			t.Fatal("invalid metadata", bad)
		}
	}
	a.Remove(aid)
	if _, ok := a.Lookup(aid); ok {
		t.Fatal("closed ID revived")
	}
	next, e := a.Add(1, 99, 0)
	if e != nil || next == aid {
		t.Fatal("wire ID reused", next, e)
	}
	a.Clear()
	if _, ok := a.Lookup(next); ok {
		t.Fatal("clear retained mapping")
	}
	if _, ok := b.Lookup(bid); !ok {
		t.Fatal("other session affected")
	}
	a.next = ^uint32(0)
	if _, e := a.Add(1, 999, 0); e == nil {
		t.Fatal("ID wrap accepted")
	}
}

func TestRegistryReservesLastStatementAlias(t *testing.T) {
	r, _ := NewRegistry(1)
	r.next = ^uint32(0) - 2
	id, err := r.Add(1, 99, 0)
	if err != nil || id != ^uint32(0)-1 {
		t.Fatal("last ordinary ID", id, err)
	}
	if _, err = r.Add(1, 100, 0); err == nil {
		t.Fatal("reserved alias allocated as an ordinary ID")
	}
	if _, ok := r.Lookup(^uint32(0)); ok {
		t.Fatal("reserved alias has a registry entry")
	}
	r.Clear()
	if _, err = r.Add(1, 101, 0); err == nil {
		t.Fatal("clear reset exhausted ID space")
	}
}
