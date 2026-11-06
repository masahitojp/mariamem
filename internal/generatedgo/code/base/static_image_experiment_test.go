//go:build (darwin && arm64) || (linux && amd64)

package base

import (
	"errors"
	"os"
	"syscall"
	"testing"
)

func TestStaticImageFailureOwnership(t *testing.T) {
	f, err := os.CreateTemp(t.TempDir(), "image-")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	const max = 3 * 65536
	if err = f.Truncate(max); err != nil {
		t.Fatal(err)
	}
	fd := int(f.Fd())
	before := MemoryMappingStats()
	_, err = newStaticImageMapping(fd, 65536, max, func(int, int64, int, int, int) ([]byte, error) { return nil, syscall.ENOMEM }, syscall.Mprotect, syscall.Munmap)
	if !errors.Is(err, syscall.ENOMEM) || MemoryMappingStats()["creates"] != before["creates"] {
		t.Fatal("reserve failure", err)
	}
	_, err = newStaticImageMapping(fd, 65536, max, syscall.Mmap, func([]byte, int) error { return syscall.ENOMEM }, func([]byte) error { return syscall.EBUSY })
	var debt *MemoryReleaseError
	if !errors.Is(err, syscall.ENOMEM) || !errors.Is(err, syscall.EBUSY) || !errors.As(err, &debt) {
		t.Fatal("lost initial cleanup debt", err)
	}
	debt.owner.unmap = syscall.Munmap
	if err = debt.Close(); err != nil {
		t.Fatal(err)
	}
	b, err := NewStaticImageMapping(fd, 65536, max)
	if err != nil {
		t.Fatal(err)
	}
	protect := b.protect
	b.protect = func([]byte, int) error { return syscall.ENOMEM }
	if err = b.Grow(65536, 2*65536); !errors.Is(err, syscall.ENOMEM) || b.enabled != 65536 {
		t.Fatal("grow failure", err)
	}
	b.protect = protect
	if err = b.Grow(65536, 2*65536); err != nil || b.memory[65536] != 0 {
		t.Fatal("grow retry", err)
	}
	b.unmap = func([]byte) error { return syscall.EBUSY }
	if err = b.Close(); !errors.Is(err, syscall.EBUSY) || b.memory == nil {
		t.Fatal("close lost owner", err)
	}
	b.unmap = syscall.Munmap
	if err = b.Close(); err != nil {
		t.Fatal(err)
	}
	if err = b.Close(); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"active_mappings", "active_rw_bytes", "active_reserved_bytes"} {
		if MemoryMappingStats()[key] != before[key] {
			t.Fatal("counter debt", key)
		}
	}
	if err = f.Truncate(65536); err != nil {
		t.Fatal(err)
	}
	if _, err = NewStaticImageMapping(fd, 65536, max); !errors.Is(err, syscall.EINVAL) {
		t.Fatal("short backing admitted", err)
	}
	if _, err = NewStaticImageMapping(-1, 65536, max); !errors.Is(err, syscall.EBADF) {
		t.Fatal("bad FD admitted", err)
	}
}
