package generatedgo

import (
	"encoding/binary"
	"testing"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

func TestHostDuplicateDescriptorContracts(t *testing.T) {
	for _, closeOriginal := range []bool{false, true} {
		t.Run(map[bool]string{true: "original-first", false: "duplicate-first"}[closeOriginal], func(t *testing.T) {
			m := trapTestModule()
			fs := base.NewBlockMemFS()
			if err := fs.WriteFile("value", []byte("abcdef"), 0600); err != nil {
				t.Fatal(err)
			}
			w := base.DefaultWASI()
			w.SetFS(fs)
			h := &host{WasiStubs: w, fdFlags: map[int32]uint16{0: 0, 1: 0, 2: 0, 3: 0}}
			defer w.CloseDescriptors()
			copy(m.Memory[64:], "value")
			if rc := h.Path_open2(m, 3, 0, 64, 5, 0, 2|4, 0, 0, 1, 128); rc != 0 {
				t.Fatal("open", rc)
			}
			original := int32(binary.LittleEndian.Uint32(m.Memory[128:]))
			binary.LittleEndian.PutUint32(m.Memory[132:], 0xfeed)
			for _, bad := range []struct{ fd, out, want int32 }{{-1, 132, 8}, {9999, 132, 8}, {original, 65534, 21}} {
				if rc := h.Fd_dup(m, bad.fd, bad.out); rc != bad.want {
					t.Fatalf("invalid duplicate %+v: %d", bad, rc)
				}
			}
			if binary.LittleEndian.Uint32(m.Memory[132:]) != 0xfeed {
				t.Fatal("failed duplicate modified output")
			}
			if rc := h.Fd_dup(m, original, 132); rc != 0 {
				t.Fatal(rc)
			}
			duplicate := int32(binary.LittleEndian.Uint32(m.Memory[132:]))
			if duplicate == original {
				t.Fatal("duplicate reused source fd")
			}
			for _, c := range []struct {
				fd    int32
				flags uint16
			}{{original, 1}, {duplicate, 0}} {
				if rc := h.Fd_fdflags_get(m, c.fd, 136); rc != 0 || binary.LittleEndian.Uint16(m.Memory[136:]) != c.flags {
					t.Fatal("per-descriptor flags", c, rc)
				}
			}
			if rc := h.Fd_seek(m, original, 2, 0, 144); rc != 0 {
				t.Fatal(rc)
			}
			if rc := h.Fd_seek(m, duplicate, 0, 1, 144); rc != 0 || binary.LittleEndian.Uint64(m.Memory[144:]) != 2 {
				t.Fatal("offset is not shared", rc)
			}
			first, last := duplicate, original
			if closeOriginal {
				first, last = original, duplicate
			}
			if rc := h.Fd_close(m, first); rc != 0 {
				t.Fatal(rc)
			}
			if rc := h.Fd_seek(m, last, 0, 1, 144); rc != 0 || binary.LittleEndian.Uint64(m.Memory[144:]) != 2 {
				t.Fatal("first close invalidated alias", rc)
			}
			if rc := h.Fd_close(m, last); rc != 0 {
				t.Fatal(rc)
			}
			if rc := h.Fd_seek(m, last, 0, 1, 144); rc != 8 {
				t.Fatal("final close retained descriptor", rc)
			}
			if rc := h.Fd_fdflags_get(m, last, 136); rc != 8 {
				t.Fatal("final close retained flags", rc)
			}
		})
	}
}
