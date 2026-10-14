package generatedgo

import (
	"errors"
	"io/fs"
	"os"
	"path/filepath"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/snapshot"
)

type directMemFS struct{ *base.MemFS }

func (f directMemFS) Open(name string) (fs.File, error) {
	return f.OpenFile(name, os.O_RDONLY, 0)
}

// Only used by the isolated temporary-Snapshot spike. Original diagnostic and
// persisted export entrypoints remain unchanged.
func exportInstance(mem *base.MemFS, transfer string) error {
	request, err := os.ReadFile(filepath.Join(transfer, snapshot.DirectRequest))
	if errors.Is(err, os.ErrNotExist) {
		return exportTransfer(mem, transfer)
	}
	if err != nil {
		return err
	}
	if len(request) == 0 || !filepath.IsAbs(string(request)) {
		return errors.New("invalid direct snapshot request")
	}
	source, err := fs.Sub(directMemFS{mem}, "snapshot-out/data")
	if err != nil {
		return err
	}
	return snapshot.MaterializeDirect(source, string(request), GuestSHA256)
}
