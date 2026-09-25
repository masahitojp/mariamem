package host

import "testing"

func TestSlotReservationAndReuse(t *testing.T) {
	s := &Server{slots: make([]bool, 3)}
	for want := uint32(0); want < 3; want++ {
		got, ok := s.allocateSlotLocked()
		if !ok || got != want {
			t.Fatalf("allocated slot %d, want %d", got, want)
		}
	}
	if _, ok := s.allocateSlotLocked(); ok {
		t.Fatal("allocated beyond advertised capacity")
	}
	s.slots[1] = false // The session worker releases only after guest close.
	if got, ok := s.allocateSlotLocked(); !ok || got != 1 {
		t.Fatalf("released slot not reusable: %d %v", got, ok)
	}
}
