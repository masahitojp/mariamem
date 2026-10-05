// Experimental diagnostic host. Unimplemented contracts panic, never succeed.
package generatedgo

import (
	"encoding/binary"
	"fmt"
	"github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"path/filepath"
	"runtime"
	"runtime/debug"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"
)

type host struct {
	*base.WasiStubs
	signalCallback string
	flagsMu        sync.Mutex
	fdFlags        map[int32]uint16
}

var diagnostic = true

func trace(args ...any) {
	if diagnostic {
		fmt.Fprintln(os.Stderr, args...)
	}
}
func tracef(format string, args ...any) {
	if diagnostic {
		fmt.Fprintf(os.Stderr, format, args...)
	}
}

// Private MemFS with ONLY explicit read-only OS entropy devices. No host-root FS.
type entropyFS struct{ *base.MemFS }

func entropyPath(name string) bool {
	name = strings.TrimPrefix(name, "/")
	return name == "dev/urandom" || name == "dev/random"
}
func (f entropyFS) OpenFile(name string, flags int, mode os.FileMode) (base.File, error) {
	if entropyPath(name) {
		if flags != os.O_RDONLY {
			return nil, os.ErrPermission
		}
		return os.Open("/" + strings.TrimPrefix(name, "/"))
	}
	return f.MemFS.OpenFile(name, flags, mode)
}
func (f entropyFS) Stat(name string) (os.FileInfo, error) {
	if entropyPath(name) {
		return os.Stat("/" + strings.TrimPrefix(name, "/"))
	}
	return f.MemFS.Stat(name)
}
func (f entropyFS) Lstat(name string) (os.FileInfo, error) { return f.Stat(name) }

// A fresh process inherits no overridden signal dispositions in this experiment.
// Delivery and thread_signal remain fail-closed until explicitly implemented.
func (h *host) Proc_signals_sizes_get(m *base.Module, out int32) int32 {
	if out < 0 || uint64(out)+4 > m.MemSize.Load() {
		return 21
	}
	binary.LittleEndian.PutUint32(m.Memory[out:], 0)
	trace("generated-Go inherited signal dispositions=0")
	return 0
}
func (h *host) Proc_signals_get(m *base.Module, out int32) int32 { return 0 }
func (h *host) Callback_signal(m *base.Module, ptr, length int32) {
	if ptr < 0 || length < 0 || uint64(ptr)+uint64(length) > m.MemSize.Load() {
		panic("signal callback bounds")
	}
	h.signalCallback = string(m.Memory[ptr : ptr+length])
	if h.signalCallback != "__wasm_signal" {
		panic("unknown signal callback: " + h.signalCallback)
	}
	trace("generated-Go registered signal callback", h.signalCallback)
}

// No chdir import exists in this artifact; each MemFS starts at its private root.
func (h *host) Getcwd(m *base.Module, out, lengthPtr int32) int32 {
	if lengthPtr < 0 || uint64(lengthPtr)+4 > m.MemSize.Load() {
		return 21
	}
	n := binary.LittleEndian.Uint32(m.Memory[lengthPtr:])
	binary.LittleEndian.PutUint32(m.Memory[lengthPtr:], 1)
	if n < 1 {
		return 68
	} // WASI ERANGE
	if out == 0 {
		return 28
	} // WASI EINVAL
	if out < 0 || uint64(out)+uint64(n) > m.MemSize.Load() {
		return 21
	}
	m.Memory[out] = '/'
	if n > 1 {
		m.Memory[out+1] = 0
	}
	trace("generated-Go getcwd=/")
	return 0
}

// One guest process per probe; no guest process creation import is present.
func (h *host) Proc_id(m *base.Module, out int32) int32 {
	if out < 0 || uint64(out)+4 > m.MemSize.Load() {
		return 21
	}
	binary.LittleEndian.PutUint32(m.Memory[out:], uint32(os.Getpid()))
	trace("generated-Go proc_id")
	return 0
}
func (h *host) Thread_parallelism(m *base.Module, out int32) int32 {
	if out < 0 || uint64(out)+4 > m.MemSize.Load() {
		return 21
	}
	binary.LittleEndian.PutUint32(m.Memory[out:], uint32(runtime.NumCPU()))
	trace("generated-Go thread_parallelism", runtime.NumCPU())
	return 0
}

// Same bounded normal-worker exit established by the earlier reduction.
func (h *host) Thread_exit(m *base.Module, code int32) {
	if code != 0 {
		panic(fmt.Sprintf("unsupported worker exit code=%d", code))
	}
	runtime.Goexit()
}

// Bounded wait/wake mapping: shared-memory queues from the existing generator.
// This excludes signal interruption, cancellation, fork and snapshot lifecycle.
func (h *host) Futex_wait(m *base.Module, addr, expected, timeout, result int32) int32 {
	if addr < 0 || uint64(addr)+4 > m.MemSize.Load() || addr%4 != 0 || timeout < 0 || uint64(timeout)+16 > m.MemSize.Load() || result < 0 || uint64(result)+1 > m.MemSize.Load() {
		return 21
	}
	duration := int64(-1)
	switch m.Memory[timeout] {
	case 0:
	case 1:
		ns := binary.LittleEndian.Uint64(m.Memory[timeout+8:])
		if ns > uint64(1<<63-1) {
			panic("futex duration overflows Go time.Duration")
		}
		duration = int64(ns)
	default:
		panic("invalid futex OptionTimestamp tag")
	}
	rc := base.AtomicWait32At(m, uint64(addr), expected, duration)
	m.Memory[result] = 1
	if rc == 2 {
		m.Memory[result] = 0
	}
	return 0
}
func (h *host) futexWake(m *base.Module, addr, out, count int32) int32 {
	if addr < 0 || uint64(addr)+4 > m.MemSize.Load() || addr%4 != 0 || out < 0 || uint64(out)+1 > m.MemSize.Load() {
		return 21
	}
	base.AtomicNotify(m, addr, 0, count)
	m.Memory[out] = 1 // Wasmer 7.4.2 returns true even when no waiter exists.
	return 0
}
func (h *host) Futex_wake(m *base.Module, addr, out int32) int32 { return h.futexWake(m, addr, out, 1) }
func (h *host) Futex_wake_all(m *base.Module, addr, out int32) int32 {
	return h.futexWake(m, addr, out, 1<<31-1)
}

func shimCheck(h *host, m *base.Module) {
	// Unused scratch beyond the guest's initial data/stack; separate check process.
	const addr, timeout, result, woke = 30000000, 30000008, 30000024, 30000025
	atomic.StoreUint32((*uint32)(unsafe.Pointer(&m.Memory[addr])), 1)
	m.Memory[timeout] = 0
	if h.Futex_wait(m, addr, 2, timeout, result) != 0 || m.Memory[result] != 1 {
		panic("futex changed-value ABI")
	}
	m.Memory[timeout] = 1
	binary.LittleEndian.PutUint64(m.Memory[timeout+8:], 1000000)
	if h.Futex_wait(m, addr, 1, timeout, result) != 0 || m.Memory[result] != 0 {
		panic("futex timeout ABI")
	}
	m.Memory[timeout] = 0
	done := make(chan struct{})
	base.ThreadLaunch(m, func(child *base.Module, tid int32) { h.Futex_wait(child, addr, 1, timeout, result); close(done) })
	limit := time.NewTimer(time.Second)
	defer limit.Stop()
	tick := time.NewTicker(time.Millisecond)
	defer tick.Stop()
	for {
		select {
		case <-done:
			if m.Memory[result] != 1 || m.Memory[woke] != 1 {
				panic("futex wake ABI")
			}
			fmt.Fprintln(os.Stderr, "generated-Go futex changed-value / timeout / blocking-wake PASS")
			return
		case <-tick.C:
			h.Futex_wake(m, addr, woke)
		case <-limit.C:
			panic("futex wake hung")
		}
	}
}

func (h *host) Path_open2(m *base.Module, fd, flags, path, length, oflags int32, rights, inherited int64, fdflags, extflags, out int32) int32 {
	if extflags & ^int32(1) != 0 {
		panic(fmt.Sprintf("unsupported path_open2 extflags=%d", extflags))
	}
	errno := base.OpenRelative(h.WasiStubs, m, fd, flags, path, length, oflags, rights, inherited, fdflags, out)
	if errno == 0 {
		h.flagsMu.Lock()
		h.fdFlags[int32(binary.LittleEndian.Uint32(m.Memory[out:]))] = uint16(extflags)
		h.flagsMu.Unlock()
	}
	if path >= 0 && length >= 0 && uint64(path)+uint64(length) <= m.MemSize.Load() {
		tracef("generated-Go path_open2 %q errno=%d\n", m.Memory[path:path+length], errno)
	}
	return errno
}
func (h *host) Fd_fdflags_set(m *base.Module, fd, flags int32) int32 {
	if flags & ^int32(1) != 0 {
		return 52
	}
	h.flagsMu.Lock()
	defer h.flagsMu.Unlock()
	if _, ok := h.fdFlags[fd]; !ok {
		return 8
	}
	h.fdFlags[fd] = uint16(flags)
	return 0
}
func (h *host) Fd_fdflags_get(m *base.Module, fd, out int32) int32 {
	if out < 0 || uint64(out)+2 > m.MemSize.Load() {
		return 21
	}
	h.flagsMu.Lock()
	defer h.flagsMu.Unlock()
	flags, ok := h.fdFlags[fd]
	if !ok {
		return 8
	}
	binary.LittleEndian.PutUint16(m.Memory[out:], flags)
	return 0
}
func (h *host) Fd_close(m *base.Module, fd int32) int32 {
	rc := h.WasiStubs.Fd_close(m, fd)
	if rc == 0 {
		h.flagsMu.Lock()
		delete(h.fdFlags, fd)
		h.flagsMu.Unlock()
	}
	return rc
}

func run(args []string) {
	// Selected candidate: bind compiled code to the host-verified module.
	transfer, restore := "", ""
	if len(args) > 2 && args[1] == "run" {
		verifyCompiledGuest(args[2])
		for i := 3; i < len(args); i++ {
			switch args[i] {
			case "--no-tty":
			case "--volume":
				i++
				if i >= len(args) {
					panic("missing volume")
				}
				v := args[i]
				if strings.HasSuffix(v, ":/snapshot-out") {
					transfer = strings.TrimSuffix(v, ":/snapshot-out")
				} else if strings.HasSuffix(v, ":/snapshot-in") {
					restore = strings.TrimSuffix(v, ":/snapshot-in")
				} else {
					panic("unexpected mount")
				}
			case "--env":
				i++
				if i >= len(args) {
					panic("missing env")
				}
			case "--":
				i = len(args)
			default:
				panic("unexpected argument")
			}
		}
		diagnostic = false
	}

	defer func() {
		if p := recover(); p != nil {
			fmt.Fprintf(os.Stderr, "generated-Go failure: %v\n%s", p, debug.Stack())
			os.Exit(1)
		}
	}()
	w := base.DefaultWASI()
	fs := base.NewMemFS()
	if err := fs.MkdirAll("dev", 0755); err != nil {
		panic(err)
	}
	if err := fs.MkdirAll("snapshot-out", 0755); err != nil {
		panic(err)
	}
	w.SetFS(entropyFS{fs})
	w.SetArgs([]string{"mariamem"})
	var maps *base.PreparedFiles
	if restore != "" {
		var err error
		maps, err = base.MapPreparedFiles(fs, filepath.Join(restore, "data"), "mariadb")
		if err != nil {
			panic(err)
		}
	}
	if len(args) == 2 && args[1] == "auth-check" {
		w.SetArgs([]string{"mariamem", "--check-auth-keys"})
	}
	if len(args) == 2 && args[1] == "measure" {
		diagnostic = false
	}
	w.SetEnv([]string{"MARIAMEM_GUEST_TIMING=1"})
	if !diagnostic {
		w.SetEnv(nil)
	}
	w.SetStdin(os.Stdin)
	w.SetStdout(os.Stdout)
	w.SetStderr(os.Stderr)
	h := &host{WasiStubs: w, fdFlags: map[int32]uint16{0: 0, 1: 0, 2: 0, 3: 0}}
	trace("generated-Go instantiate_begin (explicit MemFS)")
	m, release, allocErr := newMemoryModule(h)
	if allocErr != nil {
		panic(allocErr)
	}
	var memoryErr error
	defer func() {
		releaseMemoryModule(m, release, &memoryErr)
		if memoryErr != nil {
			panic(memoryErr)
		}
	}()
	trace("generated-Go instantiated")
	if len(args) == 2 && args[1] == "instantiate" {
		return
	}
	if len(args) == 2 && args[1] == "shim-check" {
		shimCheck(h, m)
		return
	}
	trace("generated-Go start_begin")
	generated.Start(m)
	trace("generated-Go start_returned")
	base.SpikeWait(m)
	trace("generated-Go all generated workers joined")
	if transfer != "" {
		if err := exportTransfer(fs, transfer); err != nil {
			panic(err)
		}
	}
	if err := maps.Close(); err != nil {
		panic(err)
	}
}

func (h *host) Fd_dup(m *base.Module, l0 int32, l1 int32) int32 { panic("unimplemented WASIX: Fd_dup") }
func (h *host) Fd_dup2(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32) int32 {
	panic("unimplemented WASIX: Fd_dup2")
}
func (h *host) Thread_signal(m *base.Module, l0 int32, l1 int32) int32 {
	panic("unimplemented WASIX: Thread_signal")
}
func (h *host) Proc_exit2(m *base.Module, l0 int32) { panic("unimplemented WASIX: Proc_exit2") }
func (h *host) Sock_addr_local(m *base.Module, l0 int32, l1 int32) int32 {
	panic("unimplemented WASIX: Sock_addr_local")
}
func (h *host) Sock_addr_peer(m *base.Module, l0 int32, l1 int32) int32 {
	panic("unimplemented WASIX: Sock_addr_peer")
}
func (h *host) Sock_open(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32) int32 {
	panic("unimplemented WASIX: Sock_open")
}
func (h *host) Sock_set_opt_flag(m *base.Module, l0 int32, l1 int32, l2 int32) int32 {
	panic("unimplemented WASIX: Sock_set_opt_flag")
}
func (h *host) Sock_set_opt_time(m *base.Module, l0 int32, l1 int32, l2 int32) int32 {
	panic("unimplemented WASIX: Sock_set_opt_time")
}
func (h *host) Sock_set_opt_size(m *base.Module, l0 int32, l1 int32, l2 int64) int32 {
	panic("unimplemented WASIX: Sock_set_opt_size")
}
func (h *host) Sock_get_opt_size(m *base.Module, l0 int32, l1 int32, l2 int32) int32 {
	panic("unimplemented WASIX: Sock_get_opt_size")
}
func (h *host) Sock_bind(m *base.Module, l0 int32, l1 int32) int32 {
	panic("unimplemented WASIX: Sock_bind")
}
func (h *host) Sock_connect(m *base.Module, l0 int32, l1 int32) int32 {
	panic("unimplemented WASIX: Sock_connect")
}
func (h *host) Sock_send_to(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32) int32 {
	panic("unimplemented WASIX: Sock_send_to")
}
func (h *host) Resolve(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32) int32 {
	panic("unimplemented WASIX: Resolve")
}

func (f entropyFS) Readlink(name string) (string, error) {
	if _, err := f.Stat(name); err != nil {
		return "", err
	}
	return "", &os.PathError{Op: "readlink", Path: name, Err: syscall.EINVAL}
}

func (h *host) Path_readlink(m *base.Module, fd, ptr, n, buf, size, out int32) int32 {
	return base.ReadlinkRelative(h.WasiStubs, m, fd, ptr, n, buf, size, out)
}
func (h *host) Path_filestat_get(m *base.Module, fd, flags, ptr, n, out int32) int32 {
	return base.StatRelative(h.WasiStubs, m, fd, flags, ptr, n, out)
}

// Diagnostic transport adapter; production provenance/identity binding is absent.
func loadTransfer(fs *base.MemFS, dir, prefix string) error {
	return filepath.WalkDir(dir, func(p string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		rel, e := filepath.Rel(dir, p)
		if e != nil {
			return e
		}
		dest := filepath.Join(prefix, rel)
		if d.IsDir() {
			return fs.MkdirAll(dest, 0700)
		}
		if !d.Type().IsRegular() {
			return fmt.Errorf("non-regular prepared file")
		}
		b, e := os.ReadFile(p)
		if e != nil {
			return e
		}
		return fs.WriteFile(dest, b, 0600)
	})
}
func exportTransfer(fs *base.MemFS, dest string) error {
	if _, e := fs.Stat("snapshot-out/data"); os.IsNotExist(e) {
		return nil
	} else if e != nil {
		return e
	}
	var walk func(string, string) error
	walk = func(src, dst string) error {
		f, e := fs.OpenFile(src, os.O_RDONLY, 0)
		if e != nil {
			return e
		}
		defer f.Close()
		st, e := f.Stat()
		if e != nil {
			return e
		}
		if st.IsDir() {
			if e = os.MkdirAll(dst, 0700); e != nil {
				return e
			}
			entries, e := f.ReadDir(-1)
			if e != nil {
				return e
			}
			for _, d := range entries {
				if e = walk(filepath.Join(src, d.Name()), filepath.Join(dst, d.Name())); e != nil {
					return e
				}
			}
			return nil
		}
		b := make([]byte, st.Size())
		_, e = f.ReadAt(b, 0)
		if e != nil && len(b) > 0 {
			return e
		}
		return os.WriteFile(dst, b, 0600)
	}
	return walk("snapshot-out/data", filepath.Join(dest, "data"))
}

// The host still validates manifest/module/snapshot trust. This additional
// check prevents presenting a different validated WASM to this compiled guest.
func verifyCompiledGuest(name string) {
	if name != GuestSHA256 {
		panic("compiled guest identity mismatch")
	}
}
