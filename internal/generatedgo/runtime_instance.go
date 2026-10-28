// Handwritten production execution adapter; not wasm2go-generated source.
package generatedgo

import (
	"errors"
	"fmt"
	"io"
	"sync"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/prepared"
)

var libraryMode sync.Once

// StartInstance owns fresh execution/FS state. Completion includes all guest
// workers, descriptor cleanup, snapshot export and prepared mapping release.
// It does not serialize execution or forcibly kill non-cooperative Go workers.
// StartInstance reports a fatal worker trap before joining workers.
// onFailure must not block. The returned channel still means complete cleanup;
// early failure never authorizes releasing memory owned by a running worker.
func StartInstance(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), captures ...*prepared.Capture) <-chan error {
	return startInstance(in, out, stderr, transfer, restore, guestTiming, onFailure, newMemoryModule, captures...)
}

func startInstance(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), construct func(*host) (*base.Module, func() error, error), captures ...*prepared.Capture) <-chan error {
	// CLI diagnostic entrypoints are separate command modes, not library calls.
	libraryMode.Do(func() { diagnostic = false })
	done := make(chan error, 1)
	go func() {
		var err error
		defer func() {
			if p := recover(); p != nil {
				err = errors.Join(err, guestFailure(p))
			}
			done <- err
		}()
		w := base.DefaultWASI()
		fs := base.NewBlockMemFS()
		if len(captures) > 0 && captures[0] != nil {
			if err = captures[0].BindRootSource(fs.RootSource(), GuestSHA256); err != nil {
				return
			}
		}
		if err = fs.MkdirAll("dev", 0755); err != nil {
			return
		}
		if err = fs.MkdirAll("snapshot-out", 0755); err != nil {
			return
		}
		w.SetFS(entropyFS{fs})
		w.SetArgs([]string{"mariamem"})
		w.SetEnv(guestEnvironment(restore != nil, guestTiming))
		w.SetStdin(in)
		w.SetStdout(out)
		w.SetStderr(stderr)
		var maps *base.PreparedFiles
		defer func() { err = errors.Join(err, w.CloseDescriptors(), maps.Close()) }()
		if restore != nil {
			maps, err = base.MapPreparedHandles(fs, restore, "mariadb")
			if err != nil {
				return
			}
		}
		h := &host{WasiStubs: w, fdFlags: map[int32]uint16{0: 0, 1: 0, 2: 0, 3: 0}}
		m, release, allocErr := construct(h)
		if allocErr != nil {
			err = allocErr
			return
		}
		defer releaseMemoryModule(m, release, &err)
		m.Threads.NotifyWorkerFailure(func(cause any) {
			if onFailure != nil {
				onFailure(guestFailure(cause))
			}
		})
		if err = executeGuest(m, generated.Start); err != nil {
			return
		}
		if len(captures) > 0 && captures[0] != nil && captures[0].Requested() {
			err = fs.FreezeRoot(GuestSHA256, captures[0])
			return
		}
		if transfer != "" {
			err = exportTransfer(fs, transfer)
		}
	}()
	return done
}

// executeGuest is the recover boundary for both the root and joined workers.
// Join before callers close descriptors/prepared files, including root failures.
// It intentionally retains the existing non-cooperative-worker limitation.
func executeGuest(m *base.Module, start func(*base.Module)) (err error) {
	defer func() {
		root := recover()
		var worker any
		if m != nil && m.Threads != nil {
			worker = m.Threads.WaitThreads()
		}
		for _, p := range []any{root, worker} {
			if p != nil {
				err = errors.Join(err, guestFailure(p))
			}
		}
	}()
	start(m)
	return nil
}

// Preserve owned cleanup errors through recover, including retryable munmap errors.
func guestFailure(p any) error {
	if e, ok := p.(error); ok {
		return fmt.Errorf("generated-Go guest failure: %w", e)
	}
	return fmt.Errorf("generated-Go guest failure: %v", p)
}

// Construct per-instance guest context; ambient process variables are not inputs.
func guestEnvironment(restore, guestTiming bool) []string {
	mode := "fresh"
	if restore {
		mode = "restore"
	}
	values := []string{"MARIAMEM_BOOT_MODE=" + mode}
	if guestTiming {
		values = append(values, "MARIAMEM_GUEST_TIMING=1")
	}
	return values
}
