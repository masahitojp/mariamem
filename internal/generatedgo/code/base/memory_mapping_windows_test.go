package base

import (
	"testing"
	"unsafe"
)

func TestWindowsLinearMemoryOwnership(t *testing.T) {
	before := MemoryMappingStats()
	m, err := NewMemoryMapping(65536, 4*65536)
	if err != nil {
		t.Fatal(err)
	}
	defer m.Close()
	start := unsafe.Pointer(&m.Bytes()[0])
	for _, v := range m.Bytes()[:65536] {
		if v != 0 {
			t.Fatal("reservation not zeroed")
		}
	}
	m.Bytes()[17] = 91
	if err := m.Grow(65536, 2*65536); err != nil {
		t.Fatal(err)
	}
	if unsafe.Pointer(&m.Bytes()[0]) != start || m.Bytes()[17] != 91 {
		t.Fatal("grow changed address or old bytes")
	}
	for _, v := range m.Bytes()[65536 : 2*65536] {
		if v != 0 {
			t.Fatal("new pages not zeroed")
		}
	}
	if err := m.Grow(0, 65536); err == nil {
		t.Fatal("invalid growth accepted")
	}
	if err := m.Close(); err != nil {
		t.Fatal(err)
	}
	if err := m.Close(); err != nil {
		t.Fatal(err)
	}
	after := MemoryMappingStats()
	for _, key := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes"} {
		if after[key] != before[key] {
			t.Fatalf("%s leaked: %v -> %v", key, before[key], after[key])
		}
	}
	if err := m.Grow(0, 65536); err == nil {
		t.Fatal("growth after close accepted")
	}
}
