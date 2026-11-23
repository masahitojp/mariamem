package entropyfs

import (
	"errors"
	"io"
	"os"
	"testing"
)

func TestEntropyDevicesReadOnlyAndClose(t *testing.T) {
	for _, name := range []string{"/dev/random", "/dev/urandom"} {
		st, err := Stat(name)
		if err != nil {
			t.Fatal(err)
		}
		if st.Mode()&os.ModeCharDevice == 0 || st.IsDir() {
			t.Fatalf("not a character device: %v", st)
		}
		f, err := Open(name)
		if err != nil {
			t.Fatal(err)
		}
		var data [128]byte
		if n, err := io.ReadFull(f, data[:]); n != len(data) || err != nil {
			f.Close()
			t.Fatal(n, err)
		}
		if _, err := f.Write([]byte("x")); err == nil {
			f.Close()
			t.Fatal("writable entropy device")
		}
		if err := f.Close(); err != nil {
			t.Fatal(err)
		}
		if _, err := f.Read(data[:]); !errors.Is(err, os.ErrClosed) {
			t.Fatal("closed read", err)
		}
	}
	if _, err := Open("/other"); !errors.Is(err, os.ErrNotExist) {
		t.Fatal(err)
	}
	if _, err := Stat("/dev/urandom/extra"); !errors.Is(err, os.ErrNotExist) {
		t.Fatal(err)
	}
}
