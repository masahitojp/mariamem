// Handwritten production execution adapter; not wasm2go-generated source.
package generatedgo

import (
	"errors"
	"fmt"
	"io"
	"path/filepath"
	"sync"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

var libraryMode sync.Once

// StartInstance owns fresh execution/FS state. Completion includes all guest
// workers, descriptor cleanup, snapshot export and prepared mapping release.
// It does not serialize execution or forcibly kill non-cooperative Go workers.
func StartInstance(in io.Reader, out, stderr io.Writer, transfer, restore string, guestTiming bool) <-chan error {
	// CLI diagnostic entrypoints are separate command modes, not library calls.
	libraryMode.Do(func() { diagnostic = false })
	done := make(chan error, 1)
	go func() {
		var err error
		defer func() {
			if p := recover(); p != nil {
				err = fmt.Errorf("generated-Go guest failure: %v", p)
			}
			done <- err
		}()
		w := base.DefaultWASI()
		fs := base.NewMemFS()
		if err = fs.MkdirAll("dev", 0755); err != nil {
			return
		}
		if err = fs.MkdirAll("snapshot-out", 0755); err != nil {
			return
		}
		w.SetFS(entropyFS{fs})
		w.SetArgs([]string{"mariamem"})
		w.SetEnv(nil)
		if guestTiming {
			w.SetEnv([]string{"MARIAMEM_GUEST_TIMING=1"})
		}
		w.SetStdin(in)
		w.SetStdout(out)
		w.SetStderr(stderr)
		var maps *base.PreparedFiles
		defer func() { err = errors.Join(err, w.CloseDescriptors(), maps.Close()) }()
		if restore != "" {
			maps, err = base.MapPreparedFiles(fs, filepath.Join(restore, "data"), "mariadb")
			if err != nil {
				return
			}
		}
		h := &host{WasiStubs: w, fdFlags: map[int32]uint16{0: 0, 1: 0, 2: 0, 3: 0}}
		m := generated.NewWithWASI(h, nil, h)
		generated.Start(m)
		base.SpikeWait(m)
		if transfer != "" {
			err = exportTransfer(fs, transfer)
		}
	}()
	return done
}
