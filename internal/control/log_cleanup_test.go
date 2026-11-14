package control

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestOwnedLogCleanupClosesBeforeRemoval(t *testing.T) {
	for _, owned := range []bool{false, true} {
		name := filepath.Join(t.TempDir(), "owned.log")
		f, err := os.OpenFile(name, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if err != nil {
			t.Fatal(err)
		}
		if err := cleanupOwnedLog(f, name, owned); err != nil {
			t.Fatal(err)
		}
		if _, err := f.Write([]byte("unexpected")); !errors.Is(err, os.ErrClosed) {
			t.Fatal("writer remains open", err)
		}
		_, err = os.Stat(name)
		if owned && !errors.Is(err, os.ErrNotExist) {
			t.Fatal("owned log remains", err)
		}
		if !owned && err != nil {
			t.Fatal("caller log removed", err)
		}
		if err := cleanupOwnedLog(f, name, owned); err != nil {
			t.Fatal("retry", err)
		}
	}
}
