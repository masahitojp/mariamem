package base

import (
	"encoding/binary"
	"os"
	"testing"
)

type countedDupFile struct {
	File
	closes int
}

func (f *countedDupFile) Close() error { f.closes++; return f.File.Close() }

func TestDuplicateLastAliasClosesUnderlyingFile(t *testing.T) {
	for _, closeOriginal := range []bool{false, true} {
		m := allocationModule()
		file, err := NewBlockMemFS().OpenFile("dup", os.O_CREATE|os.O_RDWR, 0600)
		if err != nil {
			t.Fatal(err)
		}
		f := &countedDupFile{File: file}
		w := DefaultWASI()
		w.fdTable[4] = &wasiOpen{f: f}
		w.nextFD = 5
		if rc := w.Fd_dup(m, 4, 64); rc != 0 {
			t.Fatal(rc)
		}
		alias := int32(binary.LittleEndian.Uint32(m.Memory[64:]))
		first, last := alias, int32(4)
		if closeOriginal {
			first, last = last, first
		}
		if rc := w.Fd_close(m, first); rc != 0 || f.closes != 0 {
			t.Fatal("closed underlying file before final alias", rc, f.closes)
		}
		if rc := w.Fd_close(m, last); rc != 0 || f.closes != 1 {
			t.Fatal("final alias did not close exactly once", rc, f.closes)
		}
		if err := w.CloseDescriptors(); err != nil || f.closes != 1 {
			t.Fatal("cleanup closed an already released file", err, f.closes)
		}
	}
}
