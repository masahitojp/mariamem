//go:build darwin || linux

package ownedroot

import (
	"bytes"
	"os"
	"strings"
	"syscall"
	"testing"
)

func TestActualMappedCopyAndLifetime(t *testing.T) {
	file, e := os.CreateTemp(t.TempDir(), "mapped")
	must(t, e)
	defer file.Close()
	want := bytes.Repeat([]byte{7}, 2*BlockSize+3)
	_, e = file.Write(want)
	must(t, e)
	p, e := syscall.Mmap(int(file.Fd()), 0, len(want), syscall.PROT_READ, syscall.MAP_PRIVATE)
	must(t, e)
	m := NewMeter()
	o, e := ImportMapped(p, digest(want), "guest", m)
	must(t, e)
	defer o.Close()
	must(t, syscall.Munmap(p))
	assertBytes(t, o, "mapped", want)
	var sourceHash, targetHash, copyBytes int64
	for k, c := range m.Snapshot() {
		if strings.HasPrefix(k, "mapped-source/") {
			sourceHash += c.HashBytes
		}
		if strings.HasPrefix(k, "mapped-target-verify/") {
			targetHash += c.HashBytes
		}
		if strings.HasPrefix(k, "mapped-copy/") {
			copyBytes += c.CopyBytes
		}
	}
	if sourceHash != int64(len(want)) || targetHash != int64(len(want)) || copyBytes != int64(len(want)) {
		t.Fatal("mapped controls failed")
	}
	if x, e := ImportMapped(want, digest([]byte("different")), "guest", NewMeter()); e == nil || x != nil {
		t.Fatal("mapped corruption accepted")
	}
	evidence(t, "mapped", m.Snapshot())
}
