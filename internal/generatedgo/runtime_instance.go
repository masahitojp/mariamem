// Handwritten production execution adapter; not wasm2go-generated source.
package generatedgo

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/timing"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"sync"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/prepared"
)

var libraryMode sync.Once

// StartInstance owns fresh execution/FS state. Completion includes all guest
// workers, descriptor cleanup, snapshot export and prepared mapping release.
// It does not serialize execution or forcibly kill non-cooperative Go workers.
func StartInstance(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, captures ...*prepared.Capture) <-chan error {
	// CLI diagnostic entrypoints are separate command modes, not library calls.
	libraryMode.Do(func() { diagnostic = false })
	done := make(chan error, 1)
	go func() {
		var startupRecord json.RawMessage
		diagnosticCtx := timing.WithRecorder(context.Background(), func(t timing.Trace) {
			if len(startupRecord) > 0 {
				data, _ := json.Marshal(struct {
					Operation string          `json:"operation"`
					Origin    int64           `json:"origin_ns"`
					PID       int             `json:"pid"`
					Guest     json.RawMessage `json:"guest"`
				}{"instance_guest", t.Origin, os.Getpid(), startupRecord})
				_ = os.WriteFile(filepath.Join(os.Getenv("MARIAMEM_TIMING_DIR"), strconv.Itoa(os.Getpid())+"-guest-"+strconv.FormatInt(t.Origin, 10)+".json"), data, 0600)
			}
		})
		ctx, finishTiming := timing.Begin(diagnosticCtx, "instance")
		var err error
		defer func() {
			if p := recover(); p != nil {
				err = errors.Join(err, guestFailure(p))
			}
			finishTiming()
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
		w.SetEnv(nil)
		if guestTiming {
			w.SetEnv([]string{"MARIAMEM_GUEST_TIMING=1"})
		}
		w.SetStdin(in)
		w.SetStdout(out)
		w.SetStderr(stderr)
		var maps *base.PreparedFiles
		defer func() {
			err = errors.Join(err, w.CloseDescriptors(), maps.Close())
			timing.Mark(ctx, "descriptors_prepared_closed")
		}()
		if restore != nil {
			maps, err = base.MapPreparedHandles(fs, restore, "mariadb")
			if err != nil {
				return
			}
		}
		timing.Mark(ctx, "prepared_handles_installed")
		h := &host{WasiStubs: w, fdFlags: map[int32]uint16{0: 0, 1: 0, 2: 0, 3: 0}}
		m, release, allocErr := newMemoryModule(h)
		if allocErr != nil {
			err = allocErr
			return
		}
		timing.Mark(ctx, "memory_initialized")
		defer func() { releaseMemoryModule(m, release, &err); timing.Mark(ctx, "memory_released") }()
		if err = executeGuest(m, func(m *base.Module) { defer timing.Mark(ctx, "guest_root_returned"); generated.Start(m) }); err != nil {
			return
		}
		timing.Mark(ctx, "guest_workers_joined")
		if timing.Enabled(ctx) {
			if f, e := fs.OpenFile("snapshot-out/startup-timing.json", os.O_RDONLY, 0); e == nil {
				data, e := io.ReadAll(io.LimitReader(f, 128*1024+1))
				_ = f.Close()
				if e == nil && len(data) <= 128*1024 && json.Valid(data) {
					startupRecord = data
				}
			}
			timing.Mark(ctx, "guest_diagnostics_collected")
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
