// Handwritten production execution adapter; not wasm2go-generated source.
package generatedgo

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"sync"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/timing"
)

var libraryMode sync.Once

// StartInstance owns fresh execution/FS state. Completion includes all guest
// workers, descriptor cleanup, snapshot export and prepared mapping release.
// It does not serialize execution or forcibly kill non-cooperative Go workers.
func StartInstance(ctx context.Context, in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool) <-chan error {
	// CLI diagnostic entrypoints are separate command modes, not library calls.
	libraryMode.Do(func() { diagnostic = false })
	done := make(chan error, 1)
	go func() {
		scope := "generated_fresh_lifetime"
		if restore != nil {
			scope = "generated_restore_lifetime"
		}
		lifetimeCtx, finishLifetime := timing.Begin(ctx, scope)
		defer finishLifetime()
		var err error
		defer func() {
			if p := recover(); p != nil {
				err = errors.Join(err, guestFailure(p))
			}
			done <- err
		}()
		timing.Mark(ctx, "generated_instance_begin")
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
			env := []string{"MARIAMEM_GUEST_TIMING=1"}
			if os.Getenv("MARIAMEM_INIT_DIAGNOSTICS") == "1" {
				env = append(env, "MARIAMEM_INIT_DIAGNOSTICS=1")
			}
			w.SetEnv(env)
		}
		w.SetStdin(in)
		w.SetStdout(out)
		w.SetStderr(stderr)
		var maps *base.PreparedFiles
		defer func() { err = errors.Join(err, w.CloseDescriptors(), maps.Close()) }()
		timing.Mark(ctx, "prepared_view_begin")
		if restore != nil {
			maps, err = base.MapPreparedHandles(fs, restore, "mariadb")
			if err != nil {
				return
			}
		}
		timing.Mark(ctx, "prepared_view_ready")
		h := &host{WasiStubs: w, fdFlags: map[int32]uint16{0: 0, 1: 0, 2: 0, 3: 0}}
		timing.Mark(ctx, "linear_memory_begin")
		m, release, allocErr := newMemoryModule(h)
		if allocErr != nil {
			err = allocErr
			return
		}
		defer releaseMemoryModule(m, release, &err)
		timing.Mark(ctx, "linear_memory_ready")
		timing.Mark(ctx, "generated_guest_enter")
		if err = executeGuest(m, generated.Start); err != nil {
			return
		}
		if transfer != "" {
			err = exportTransfer(fs, transfer)
			// Collect only after cooperative guest/worker join, outside ready timing.
			if timing.Enabled(lifetimeCtx) {
				if f, e := fs.OpenFile("snapshot-out/startup-timing.json", os.O_RDONLY, 0); e == nil {
					data, e := io.ReadAll(io.LimitReader(f, 128*1024+1))
					_ = f.Close()
					if e == nil {
						timing.ReadGuestBytes(lifetimeCtx, data)
					}
				}
			}
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
