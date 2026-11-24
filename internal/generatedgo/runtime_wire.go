// Handwritten production execution adapter; not wasm2go-generated source.
package generatedgo

import (
	"errors"
	"fmt"
	"io"
	"os"
	"strconv"
	"sync"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/prepared"
)

// WireLifecycle binds capture, keep-root, and stop notifications for native wire execution.
type WireLifecycle struct {
	Capture         *prepared.Capture
	Approval        <-chan error
	Observe         func(string)
	OnStopped       func(error)
	BindGuestTiming func(func() []byte)
}

func (l *WireLifecycle) observe(event string) {
	if l != nil && l.Observe != nil {
		l.Observe(event)
	}
}

var wireLibraryMode sync.Once

// StartWireInstance owns fresh execution/FS state. Completion includes all guest
// workers, descriptor cleanup, snapshot export and prepared mapping release.
func StartWireInstance(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), epoch uint64, life *WireLifecycle) <-chan error {
	return startWireInstance(in, out, stderr, transfer, restore, guestTiming, onFailure, newMemoryModule, epoch, life)
}

func startWireInstance(in io.Reader, out, stderr io.Writer, transfer string, restore []prepared.Entry, guestTiming bool, onFailure func(error), construct func(*host) (*base.Module, func() error, error), epoch uint64, life *WireLifecycle) <-chan error {
	wireLibraryMode.Do(func() { diagnostic = false })
	done := make(chan error, 1)
	go func() {
		var err error
		var stopOnce sync.Once
		notifyStopped := func(e error) {
			stopOnce.Do(func() {
				if life != nil && life.OnStopped != nil {
					life.OnStopped(e)
				}
			})
		}
		defer func() {
			if p := recover(); p != nil {
				err = errors.Join(err, wireGuestFailure(p))
			}
			notifyStopped(err)
			done <- err
		}()
		w := base.DefaultWASI()
		fs := base.NewBlockMemFS()
		if guestTiming && life != nil && life.BindGuestTiming != nil {
			life.BindGuestTiming(func() []byte {
				f, e := fs.OpenFile("snapshot-out/startup-timing.json", os.O_RDONLY, 0)
				if e != nil {
					return nil
				}
				defer f.Close()
				st, e := f.Stat()
				if e != nil || st.IsDir() || st.Size() <= 0 || st.Size() > 128*1024 {
					return nil
				}
				b := make([]byte, st.Size())
				if _, e := f.ReadAt(b, 0); e != nil {
					return nil
				}
				return b
			})
		}
		if life == nil || life.Capture == nil || life.Approval == nil {
			err = fmt.Errorf("capture lifecycle required")
			return
		}
		if err = life.Capture.BindRootSource(fs.RootSource(), GuestSHA256); err != nil {
			return
		}
		// Non-consuming SnapshotKeep root cut: identical to runtime_instance.go.
		life.Capture.SetKeep(func() (*prepared.Root, error) {
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
		if epoch == 0 || transfer != "" {
			err = fmt.Errorf("wire experiment requires nonzero instance identity and no transfer")
			return
		}
		w.SetEnv(append(wireGuestEnvironment(restore != nil, guestTiming), "MARIAMEM_CONTROL_EPOCH="+strconv.FormatUint(epoch, 10)))
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
		defer func() {
			notifyStopped(err)
			releaseMemoryModule(m, release, &err)
			life.observe("memory_released")
		}()
		m.Threads.NotifyWorkerFailure(func(cause any) {
			if onFailure != nil {
				onFailure(wireGuestFailure(cause))
			}
		})
		if err = executeWireCapture(m, generated.Start, fs, life); err != nil {
			return
		}
		if transfer != "" {
			err = exportTransfer(fs, transfer)
		}
	}()
	return done
}

func executeWireGuest(m *base.Module, start func(*base.Module)) (err error) {
	defer func() {
		root := recover()
		var worker any
		if m != nil && m.Threads != nil {
			worker = m.Threads.WaitThreads()
		}
		for _, p := range []any{root, worker} {
			if p != nil {
				err = errors.Join(err, wireGuestFailure(p))
			}
		}
	}()
	start(m)
	return nil
}

func wireGuestFailure(p any) error {
	if e, ok := p.(error); ok {
		return fmt.Errorf("generated-Go guest failure: %w", e)
	}
	return fmt.Errorf("generated-Go guest failure: %v", p)
}

func wireGuestEnvironment(restore, guestTiming bool) []string {
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

func executeWireCapture(m *base.Module, start func(*base.Module), fs *base.MemFS, life *WireLifecycle) error {
	if err := executeWireGuest(m, start); err != nil {
		return err
	}
	life.observe("guest_joined")
	if life.Capture.Requested() {
		if err := <-life.Approval; err != nil {
			return err
		}
		life.observe("capture_approved")
		life.observe("freeze_begin")
		if err := fs.FreezeRoot(GuestSHA256, life.Capture); err != nil {
			return err
		}
		life.observe("freeze_complete")
	}
	return nil
}
