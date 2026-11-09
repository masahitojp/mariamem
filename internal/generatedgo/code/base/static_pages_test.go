//go:build (darwin && arm64) || (linux && amd64)

package base

import (
	"errors"
	"os"
	"syscall"
	"testing"
)

func TestStaticPagesRangesOwnership(t *testing.T) {
	f, e := os.CreateTemp(t.TempDir(), "pages")
	if e != nil {
		t.Fatal(e)
	}
	defer f.Close()
	const initial = 2 * 65536
	const maximum = 4 * 65536
	if e = f.Truncate(maximum); e != nil {
		t.Fatal(e)
	}
	page := uint64(os.Getpagesize())
	rs := []ImageRange{{page, page}, {3 * page, page}}
	for _, r := range rs {
		if _, e = f.WriteAt([]byte{42}, int64(r.Offset)); e != nil {
			t.Fatal(e)
		}
	}
	// A nonzero byte outside selected pages must NOT appear through the mapping.
	if _, e = f.WriteAt([]byte{99}, 0); e != nil {
		t.Fatal(e)
	}
	ro, e := os.Open(f.Name())
	if e != nil {
		t.Fatal(e)
	}
	defer ro.Close()
	fd := int(ro.Fd())
	before := MemoryMappingStats()
	for _, bad := range [][]ImageRange{{{1, page}}, {{page, 0}}, {{page, page + 1}}, {{0, page}, {0, page}}, {{initial, page}}, {{0, ^uint64(0)}}, {{3 * page, page}, {page, page}}} {
		if _, e = NewStaticPageMapping(fd, initial, maximum, bad); !errors.Is(e, syscall.EINVAL) {
			t.Fatal("invalid range", bad, e)
		}
	}
	if MemoryMappingStats()["creates"] != before["creates"] {
		t.Fatal("invalid ranges allocated")
	}
	a, e := NewStaticPageMapping(fd, initial, maximum, rs)
	if e != nil {
		t.Fatal(e)
	}
	defer a.Close()
	b, e := NewStaticPageMapping(fd, initial, maximum, rs)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	if a.memory[0] != 0 || a.memory[page] != 42 || a.memory[3*page] != 42 {
		t.Fatal("page overlay")
	}
	a.memory[page] = 8
	a.memory[0] = 9
	raw := []byte{0}
	_, e = ro.ReadAt(raw, int64(page))
	if e != nil || raw[0] != 42 || b.memory[page] != 42 || b.memory[0] != 0 {
		t.Fatal("private isolation", e)
	}
	if e = a.Grow(initial, maximum); e != nil || a.memory[maximum-1] != 0 {
		t.Fatal("anonymous grow", e)
	}
	if e = a.Close(); e != nil {
		t.Fatal(e)
	}
	if b.memory[page] != 42 {
		t.Fatal("sibling lost")
	}
	if e = b.Close(); e != nil {
		t.Fatal(e)
	}
	// Mid-overlay failure must discard all replaced and anonymous segments.
	n := 0
	replace := func(addr, length uintptr, fd int, off uint64) error {
		n++
		if n == 2 {
			return syscall.ENOMEM
		}
		return replaceImagePages(addr, length, fd, off)
	}
	if _, e = newStaticPageMapping(fd, initial, maximum, rs, replace, syscall.Munmap); !errors.Is(e, syscall.ENOMEM) {
		t.Fatal("mid-overlay", e)
	}
	n = 0
	_, e = newStaticPageMapping(fd, initial, maximum, rs, replace, func([]byte) error { return syscall.EBUSY })
	var debt *MemoryReleaseError
	if !errors.Is(e, syscall.ENOMEM) || !errors.Is(e, syscall.EBUSY) || !errors.As(e, &debt) {
		t.Fatal("lost debt", e)
	}
	debt.owner.unmap = syscall.Munmap
	if e = debt.Close(); e != nil {
		t.Fatal(e)
	}
	for _, k := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes"} {
		if MemoryMappingStats()[k] != before[k] {
			t.Fatal("mapping debt", k)
		}
	}
}
