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
// onFailure must not block. The returned channel reports the cleanup attempt and any retained debt;
// early failure never authorizes releasing memory owned by a running worker.
func StartInstance(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), captures ...*prepared.Capture) <-chan error {
	return startInstance(in, out, stderr, transfer, restore, guestTiming, onFailure, newMemoryModule, captures...)
}

// StartInstanceWithStopped reports quiescence after all guest execution and
// final output, before releasing instance resources. Both channels are buffered.
// Stopped carries execution failure separately from the cleanup attempt result.
func StartInstanceWithStopped(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), captures ...*prepared.Capture) (<-chan error, <-chan error) {
	stopped := make(chan error, 1)
	completed := startInstanceWithStopped(in, out, stderr, transfer, restore, guestTiming, onFailure, newMemoryModule, func(err error) { stopped <- err }, captures...)
	return stopped, completed
}

func startInstance(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), construct func(*host) (*base.Module, func() error, error), captures ...*prepared.Capture) <-chan error {
	return startInstanceWithStopped(in, out, stderr, transfer, restore, guestTiming, onFailure, construct, nil, captures...)
}

func startInstanceWithStopped(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), construct func(*host) (*base.Module, func() error, error), onStopped func(error), captures ...*prepared.Capture) <-chan error {
	return runInstance(in, out, stderr, transfer, restore, guestTiming, onFailure, construct, onStopped, generated.Start, captures...)
}

func runInstance(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), construct func(*host) (*base.Module, func() error, error), onStopped func(error), start func(*base.Module), captures ...*prepared.Capture) <-chan error {
	// CLI diagnostic entrypoints are separate command modes, not library calls.
	libraryMode.Do(func() { diagnostic = false })
	done := make(chan error, 1)
	go func() {
		var err error
		var stopOnce sync.Once
		stopped := func() {
			stopOnce.Do(func() {
				if onStopped != nil {
					onStopped(err)
				}
			})
		}
		defer func() {
			if p := recover(); p != nil {
				err = errors.Join(err, guestFailure(p))
			}
			stopped()
			done <- err
		}()
		w := base.DefaultWASI()
		fs := base.NewBlockMemFS()
		if len(captures) > 0 && captures[0] != nil {
			if err = captures[0].BindRootSource(fs.RootSource(), GuestSHA256); err != nil {
				return
			}
			// A non-consuming cut uses its own capture binding on the same
			// root source; the consuming capture above remains unchanged.
			captures[0].SetKeep(func() (*prepared.Root, error) {
				c := new(prepared.Capture)
				if e := c.BindRootSource(fs.RootSource(), GuestSHA256); e != nil {
					return nil, e
				}
				c.Request()
				if e := fs.CutRoot(GuestSHA256, c); e != nil {
					return nil, e
				}
				return c.TakeRoot(GuestSHA256)
			})
		}
		if err = fs.MkdirAll("dev", 0755); err != nil {
			return
		}
		if err = fs.MkdirAll("snapshot-out", 0755); err != nil {
			return
		}
		// Reload pages on demand: startup preload competes with first-use SQL
		// in short-lived forks. Keep this per-instance, before guest startup.
		if err = fs.MkdirAll("etc", 0755); err != nil {
			return
		}
		if err = fs.WriteFile("etc/my.cnf", []byte("[server]\ninnodb-buffer-pool-load-at-startup=OFF\n[embedded]\ninnodb-buffer-pool-load-at-startup=OFF\n"), 0644); err != nil {
			return
		}
		w.SetFS(entropyFS{fs})
		w.SetArgs([]string{"mariamem"})
		w.SetEnv(guestEnvironment(restore != nil, guestTiming))
		w.SetStdin(in)
		w.SetStdout(out)
		w.SetStderr(stderr)
		var maps *base.PreparedFiles
		var m *base.Module
		var release func() error
		defer func() {
			// Preserve descriptor/mapping teardown even if memory teardown
			// unexpectedly panics, as with the previous separate defers.
			defer func() { err = errors.Join(err, closeDescriptors(w), retainRelease(maps.Close)) }()
			if p := recover(); p != nil {
				err = errors.Join(err, guestFailure(p))
			}
			if m != nil {
				if p := m.Threads.WaitThreads(); p != nil && err == nil {
					err = guestFailure(p)
				}
			}
			// All final output/capture/export precedes this defer. A stuck
			// worker keeps both the notification and reclamation pending.
			stopped()
			if m != nil {
				releaseMemoryModule(m, release, &err)
			}
		}()
		if restore != nil {
			maps, err = base.MapPreparedHandles(fs, restore, "mariadb")
			if err != nil {
				return
			}
		}
		h := &host{WasiStubs: w, fdFlags: map[int32]uint16{0: 0, 1: 0, 2: 0, 3: 0}}
		created, ownedRelease, allocErr := construct(h)
		if allocErr != nil {
			err = allocErr
			return
		}
		m, release = created, ownedRelease
		m.Threads.NotifyWorkerFailure(func(cause any) {
			if onFailure != nil {
				onFailure(guestFailure(cause))
			}
		})
		if err = executeGuest(m, start); err != nil {
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
