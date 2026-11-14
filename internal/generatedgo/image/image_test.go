//go:build (darwin && arm64) || (linux && amd64)

package image

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/generatedgo/imagelayout"
	"os"
	"os/exec"
	"reflect"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p8"
)

// Init completion flag written to 2 by the pinned generated p7.Fn67.
// Keep this test-only address bound to the constructor when guest data relocates.
const initialMemoryFlagOffset = 27744624

func assertInitialMemoryFlag(t *testing.T, m *base.Module) {
	t.Helper()
	if initialMemoryFlagOffset <= m.DataEnd || binary.LittleEndian.Uint32(m.Memory[initialMemoryFlagOffset:]) != 2 {
		t.Fatal("init-flag fixture no longer matches generated constructor")
	}
}

func TestMain(m *testing.M) {
	code := m.Run()
	stats := base.MemoryMappingStats()
	for _, key := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes"} {
		if stats[key] != 0 {
			fmt.Fprintln(os.Stderr, "final ownership debt", key, stats[key])
			code = 1
		}
	}
	fmt.Printf("final active mappings=%d reserved=%d rw=%d\n", stats["active_mappings"], stats["active_reserved_bytes"], stats["active_rw_bytes"])
	os.Exit(code)
}

func mustChild(t *testing.T, f *factory) *child {
	t.Helper()
	c, err := f.acquire()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := c.close(); err != nil {
			t.Error(err)
		}
	})
	return c
}

func ownedFactory(t *testing.T) *factory {
	t.Helper()
	f := newFactory(t.TempDir())
	t.Cleanup(func() {
		if err := f.close(); err != nil {
			t.Error(err)
		}
	})
	return f
}

func sameInitial(a, b *base.Module) error {
	if !bytes.Equal(a.Memory[:generated.InitialMemoryBytes], b.Memory[:generated.InitialMemoryBytes]) {
		return errors.New("initial bytes differ")
	}
	if !reflect.DeepEqual(base.SaveGlobals(a), base.SaveGlobals(b)) {
		return errors.New("globals differ")
	}
	if a.DataEnd != b.DataEnd {
		return errors.New("DataEnd differs")
	}
	if len(a.DataSegs) != len(b.DataSegs) {
		return errors.New("segment count differs")
	}
	for i := range a.DataSegs {
		if (a.DataSegs[i] == nil) != (b.DataSegs[i] == nil) || !bytes.Equal(a.DataSegs[i], b.DataSegs[i]) {
			return fmt.Errorf("segment %d differs", i)
		}
	}
	return nil
}

func TestFullInitialEqualityAndIsolation(t *testing.T) {
	before := base.MemoryMappingStats()
	normal, err := base.NewMemoryMapping(generated.InitialMemoryBytes, maximum)
	if err != nil {
		t.Fatal(err)
	}
	defer normal.Close()
	m := generated.NewWithMemory(nil, nil, nil, normal.Bytes(), generated.InitialMemoryBytes)
	f := ownedFactory(t)
	a, b := mustChild(t, f), mustChild(t, f)
	if fmt.Sprintf("%x", sha256.Sum256(m.Memory[:generated.InitialMemoryBytes])) != f.layout.MemorySHA256 {
		t.Fatal("manifest full-memory hash mismatch")
	}
	for _, c := range []*child{a, b} {
		if err := sameInitial(m, c.m); err != nil {
			t.Fatal(err)
		}
		if c.m.Threads == m.Threads || c.m.MemMu == m.MemMu || c.m.MemSize == m.MemSize || c.m.M == m.M {
			t.Fatal("shared runtime owner")
		}
	}
	if a.m.Threads == b.m.Threads || a.m.MemMu == b.m.MemMu || a.m.MemSize == b.m.MemSize || &a.m.T0[0] == &b.m.T0[0] {
		t.Fatal("siblings share module state")
	}
	assertInitialMemoryFlag(t, m)
	t.Logf("initial256MiB_sha256=%x globals=%v DataEnd=%d init_flag=%d", sha256.Sum256(m.Memory[:generated.InitialMemoryBytes]), base.SaveGlobals(m), m.DataEnd, binary.LittleEndian.Uint32(m.Memory[initialMemoryFlagOffset:]))
	// Negative controls: each known easy-to-miss state must be detected.
	a.m.G1 = 0
	if sameInitial(m, a.m) == nil {
		t.Fatal("missed TLS global mutation")
	}
	a.m.G1 = m.G1
	a.m.DataEnd = 0
	if sameInitial(m, a.m) == nil {
		t.Fatal("missed DataEnd mutation")
	}
	a.m.DataEnd = m.DataEnd
	a.m.DataSegs[0] = []byte{1}
	if sameInitial(m, a.m) == nil {
		t.Fatal("missed dropped segment mutation")
	}
	a.m.DataSegs[0] = nil
	for _, off := range []int{8388608, 18118912, 18761536, 18762048, initialMemoryFlagOffset} {
		original := m.Memory[off]
		a.m.Memory[off] ^= 0xff
		if sameInitial(m, a.m) == nil || b.m.Memory[off] != original {
			t.Fatal("isolation/oracle", off)
		}
		v := []byte{0}
		if _, err := f.image.ReadAt(v, int64(off)); err != nil || v[0] != original {
			t.Fatal("backing changed", off, err)
		}
	}
	if _, err := f.image.WriteAt([]byte{0}, 8388608); err == nil {
		t.Fatal("backing FD is writable")
	}
	if err := a.close(); err != nil {
		t.Fatal(err)
	}
	if err := sameInitial(m, b.m); err != nil {
		t.Fatal("sibling after close", err)
	}
	// Closing the cache stops new admission, but successful mappings survive.
	if err := f.close(); err != nil {
		t.Fatal(err)
	}
	if _, err := f.acquire(); !errors.Is(err, errClosed) {
		t.Fatal("admitted after close", err)
	}
	b.m.Memory[8388608] ^= 0xff
	if err := b.close(); err != nil {
		t.Fatal(err)
	}
	if err := normal.Close(); err != nil {
		t.Fatal(err)
	}
	after := base.MemoryMappingStats()
	for _, k := range []string{"active_mappings", "active_reserved_bytes", "active_rw_bytes"} {
		if after[k] != before[k] {
			t.Fatal("retained", k, before, after)
		}
	}
}

func TestWorkerTLSGrowAndRetirement(t *testing.T) {
	f := ownedFactory(t)
	c := mustChild(t, f)
	m := c.m
	ptr := m.M
	originalGrow := m.PrepareMemoryGrow
	m.PrepareMemoryGrow = func(uint64, uint64) error { return syscall.ENOMEM }
	if base.MemoryGrow(m, 1) != -1 || base.MemorySize(m) != 4096 {
		t.Fatal("failed grow published")
	}
	m.PrepareMemoryGrow = originalGrow
	if base.MemoryGrow(m, 1) != 4096 || m.M != ptr || m.Memory[generated.InitialMemoryBytes] != 0 {
		t.Fatal("grow")
	}
	generated.WasmInitTls(m, 65536)
	binary.LittleEndian.PutUint32(m.Memory[65540:], 123)
	parentTLS := m.G1
	ready, finish := make(chan bool, 1), make(chan struct{})
	base.ThreadLaunch(m, func(worker *base.Module, tid int32) {
		generated.WasmInitTls(worker, generated.InitialMemoryBytes)
		binary.LittleEndian.PutUint32(worker.Memory[generated.InitialMemoryBytes+4:], 456)
		worker.G0 = 7 << 20
		ready <- worker.M == m.M && worker.Threads == m.Threads && worker.MemSize == m.MemSize && p8.Fn68(worker) == 456
		<-finish
	})
	if !<-ready || m.G1 != parentTLS || p8.Fn68(m) != 123 || m.G0 != 8<<20 {
		t.Fatal("worker TLS")
	}
	if base.MemoryGrow(m, 32768-4097) != 4097 || m.M != ptr || m.Memory[maximum-1] != 0 {
		t.Fatal("max grow")
	}
	if base.MemoryGrow(m, 1) != -1 {
		t.Fatal("beyond max accepted")
	}
	closed := make(chan error, 1)
	go func() { closed <- c.close() }()
	select {
	case err := <-closed:
		t.Fatal("released live worker", err)
	case <-time.After(25 * time.Millisecond):
	}
	close(finish)
	if err := <-closed; err != nil {
		t.Fatal(err)
	}
}

func TestConcurrentFactoryAndFailures(t *testing.T) {
	f := ownedFactory(t)
	const n = 8
	children := make(chan *child, n)
	errs := make(chan error, n)
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); c, e := f.acquire(); children <- c; errs <- e }()
	}
	wg.Wait()
	close(children)
	close(errs)
	for e := range errs {
		if e != nil {
			t.Fatal(e)
		}
	}
	if f.builds != 1 {
		t.Fatal("multiple images", f.builds)
	}
	for c := range children {
		if err := c.close(); err != nil {
			t.Fatal(err)
		}
	}
	if err := f.close(); err != nil {
		t.Fatal(err)
	}
	t.Run("build", func(t *testing.T) {
		x := ownedFactory(t)
		x.beforeBuild = func() error { return syscall.EIO }
		for i := 0; i < 2; i++ {
			if _, e := x.acquire(); !errors.Is(e, syscall.EIO) {
				t.Fatal(e)
			}
		}
		if x.builds != 1 {
			t.Fatal("hidden rebuild")
		}
	})
	t.Run("read_open", func(t *testing.T) {
		x := ownedFactory(t)
		x.openRead = func(string) (*os.File, error) { return nil, syscall.EMFILE }
		if _, e := x.acquire(); !errors.Is(e, syscall.EMFILE) {
			t.Fatal(e)
		}
		if len(x.files) != 0 {
			t.Fatal("failed build retained a disposable writer")
		}
		if e := x.close(); e != nil {
			t.Fatal(e)
		}
		files, e := os.ReadDir(x.dir)
		if e != nil || len(files) != 0 {
			t.Fatal("temp debt", files, e)
		}
	})
	t.Run("writer_close", func(t *testing.T) {
		x := ownedFactory(t)
		x.closeFile = func(*os.File) error { return syscall.EBUSY }
		if _, e := x.acquire(); !errors.Is(e, syscall.EBUSY) {
			t.Fatal(e)
		}
		if len(x.files) != 2 {
			t.Fatal("lost unpublished owners")
		}
		x.closeFile = (*os.File).Close
		if e := x.close(); e != nil {
			t.Fatal(e)
		}
	})
	t.Run("mapping", func(t *testing.T) {
		x := ownedFactory(t)
		first := mustChild(t, x)
		x.mapImage = func(int, uint64, uint64) (*base.MemoryMapping, error) { return nil, syscall.ENOMEM }
		if _, e := x.acquire(); !errors.Is(e, syscall.ENOMEM) {
			t.Fatal(e)
		}
		first.m.Memory[8388608] ^= 0xff // Existing owner remains usable.
	})
	t.Run("cache_close", func(t *testing.T) {
		x := ownedFactory(t)
		c := mustChild(t, x)
		x.closeFile = func(*os.File) error { return syscall.EBUSY }
		if e := x.close(); !errors.Is(e, syscall.EBUSY) || len(x.files) != 1 {
			t.Fatal("lost close owner", e)
		}
		if _, e := x.acquire(); !errors.Is(e, errClosed) {
			t.Fatal(e)
		}
		c.m.Memory[8388608] ^= 0xff
		x.closeFile = (*os.File).Close
		if e := x.close(); e != nil {
			t.Fatal(e)
		}
	})
	t.Run("metadata", func(t *testing.T) {
		x := ownedFactory(t)
		mustChild(t, x)
		x.globals = nil
		if _, e := x.acquire(); e == nil {
			t.Fatal("invalid metadata accepted")
		}
	})
}

func TestGuardFault(t *testing.T) {
	if os.Getenv("STATIC_IMAGE_GUARD_CHILD") == "1" {
		f := newFactory(os.Getenv("STATIC_IMAGE_GUARD_DIR"))
		c, e := f.acquire()
		if e != nil {
			t.Fatal(e)
		}
		fmt.Println("guard-access-next")
		c.m.Memory[generated.InitialMemoryBytes] = 7 // Mapped but still PROT_NONE.
		t.Fatal("guard failed")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, os.Args[0], "-test.run=^TestGuardFault$")
	cmd.Env = append(os.Environ(), "STATIC_IMAGE_GUARD_CHILD=1", "STATIC_IMAGE_GUARD_DIR="+t.TempDir(), "GOTRACEBACK=single")
	out, err := cmd.CombinedOutput()
	if ctx.Err() != nil || err == nil || !strings.Contains(string(out), "guard-access-next") || !strings.Contains(string(out), "unexpected fault address") {
		t.Fatalf("not expected protection fault: %v %s", err, out)
	}
	t.Log("subprocess rejected write beyond logical memory with OS fault")
}

func TestConcurrentCloseAdmission(t *testing.T) {
	f := ownedFactory(t)
	existing := mustChild(t, f)
	start := make(chan struct{})
	results := make(chan error, 9)
	for i := 0; i < 8; i++ {
		go func() {
			<-start
			c, err := f.acquire()
			if errors.Is(err, errClosed) {
				results <- nil
				return
			}
			if err != nil {
				results <- err
				return
			}
			c.m.Memory[8388608] ^= 0xff
			results <- c.close()
		}()
	}
	go func() { <-start; results <- f.close() }()
	close(start)
	for i := 0; i < 9; i++ {
		if err := <-results; err != nil {
			t.Fatal(err)
		}
	}
	if _, err := f.acquire(); !errors.Is(err, errClosed) {
		t.Fatal("admission reopened", err)
	}
	if len(f.files) != 0 || f.image.Fd() != ^uintptr(0) {
		t.Fatal("cache FD retained")
	}
	existing.m.Memory[8388608] ^= 0xff
}

// DataEnd does not cover all initialized state: the init flag is farther out.
func TestPageOnlyRangeCompleteness(t *testing.T) {
	f := ownedFactory(t)
	first := mustChild(t, f)
	if len(f.ranges) == 0 {
		t.Fatal("no ranges")
	}
	var bytes uint64
	for _, r := range f.ranges {
		bytes += r.Length
	}
	if bytes >= generated.InitialMemoryBytes {
		t.Fatal("not a static-only subset")
	}
	old := append([]base.ImageRange(nil), f.ranges...)
	// Remove just the init-flag page; the full initial-memory oracle must reject it.
	page := uint64(os.Getpagesize())
	assertInitialMemoryFlag(t, first.m)
	flag := uint64(initialMemoryFlagOffset) / page * page
	removed := false
	f.ranges = nil
	for _, r := range old {
		end := r.Offset + r.Length
		if flag < r.Offset || flag >= end {
			f.ranges = append(f.ranges, r)
			continue
		}
		removed = true
		if r.Offset < flag {
			f.ranges = append(f.ranges, base.ImageRange{Offset: r.Offset, Length: flag - r.Offset})
		}
		if flag+page < end {
			f.ranges = append(f.ranges, base.ImageRange{Offset: flag + page, Length: end - flag - page})
		}
	}
	if !removed {
		t.Fatal("init-flag page was not in the image ranges")
	}
	bad := mustChild(t, f)
	if sameInitial(first.m, bad.m) == nil {
		t.Fatal("missed initialized state after DataEnd")
	}
	f.ranges = old
	t.Logf("static-page bytes=%d ranges=%d OS-page=%d init-flag-page=%d", bytes, len(old), page, flag)
}

func TestGeneratedEnvelopeEqualsFullImage(t *testing.T) {
	full, bounded := ownedFactory(t), ownedFactory(t)
	full.fullScan, bounded.fullScan = true, false
	a, b := mustChild(t, full), mustChild(t, bounded)
	if err := sameInitial(a.m, b.m); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(full.ranges, bounded.ranges) {
		t.Fatal("image ranges differ")
	}
	if bounded.scannedBytes >= full.scannedBytes || uint64(bounded.scannedBytes) < bounded.layout.End-bounded.layout.Begin {
		t.Fatal("scan bounds")
	}
	t.Logf("full=%d bounded=%d ranges=%v", full.scannedBytes, bounded.scannedBytes, bounded.ranges)
}

// The image owner and child mappings have separate lifetimes. Closing one owner
// cannot invalidate an admitted child or make a later explicit owner share state.
func TestExplicitOwnerEpochs(t *testing.T) {
	old := ownedFactory(t)
	a := mustChild(t, old)
	if err := old.close(); err != nil {
		t.Fatal(err)
	}
	if len(old.files) != 0 {
		t.Fatal("image FD retained")
	}
	if _, err := old.acquire(); !errors.Is(err, errClosed) {
		t.Fatal(err)
	}
	next := ownedFactory(t)
	b := mustChild(t, next)
	if err := sameInitial(a.m, b.m); err != nil {
		t.Fatal(err)
	}
	a.m.Memory[8388608] ^= 0xff
	if a.m.Memory[8388608] == b.m.Memory[8388608] {
		t.Fatal("epoch data shared mutably")
	}
	if old.builds != 1 || next.builds != 1 {
		t.Fatal("unexpected rebuild")
	}
}
func TestInvalidGeneratedMetadataStopsAdmission(t *testing.T) {
	f := ownedFactory(t)
	f.layout, f.layoutErr = imagelayout.Decode(layoutJSON)
	f.layout.MemoryBytes = 1
	if _, err := f.acquire(); err == nil {
		t.Fatal("invalid metadata admitted")
	}
	if _, err := f.acquire(); err == nil || f.builds != 1 {
		t.Fatal("failed owner retried or admitted")
	}
	if e := f.close(); e != nil {
		t.Fatal(e)
	}
}

func TestProcessCacheIsLazyAndReused(t *testing.T) {
	if os.Getenv("STATIC_IMAGE_PROCESS_CHILD") != "1" {
		cmd := exec.Command(os.Args[0], "-test.run=^TestProcessCacheIsLazyAndReused$")
		cmd.Env = append(os.Environ(), "STATIC_IMAGE_PROCESS_CHILD=1")
		if out, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("%v: %s", err, out)
		}
		return
	}
	before := Stats()
	if before["builds"].(int) != 0 {
		t.Fatal("process cache initialized before use")
	}
	for i := 0; i < 3; i++ {
		m, release, err := Acquire(nil, nil)
		if err != nil {
			t.Fatal(err)
		}
		m.Memory[8388608] ^= 0xff
		if err = release(); err != nil {
			t.Fatal(err)
		}
	}
	got := Stats()
	if got["builds"].(int) != 1 || got["acquires"].(int) != 3 || got["owned_fds"].(int) != 1 || got["closed"].(bool) {
		t.Fatal(got)
	}
	if base.MemoryMappingStats()["active_mappings"] != 0 {
		t.Fatal("child mapping retained")
	}
}
func TestBuildPanicLatchesAndDisposes(t *testing.T) {
	f := ownedFactory(t)
	f.beforeBuild = func() error { panic("injected constructor failure") }
	for i := 0; i < 2; i++ {
		if _, err := f.acquire(); err == nil || !strings.Contains(err.Error(), "injected") {
			t.Fatal(err)
		}
	}
	if f.builds != 1 || len(f.files) != 0 {
		t.Fatal("retry or retained file")
	}
}

// Model an unsuccessful unmap with the same retry authority as MemoryReleaseError.
type failingCleanup struct {
	attempts int
	fail     bool
}

func (d *failingCleanup) Error() string { return "injected unmap debt" }
func (d *failingCleanup) Close() error {
	d.attempts++
	if d.fail {
		return syscall.EBUSY
	}
	return nil
}
func TestMapCleanupDebtStopsAdmissionAfterRecovery(t *testing.T) {
	f := ownedFactory(t)
	survivor := mustChild(t, f)
	debt := &failingCleanup{fail: true}
	maps := 0
	f.mapImage = func(int, uint64, uint64) (*base.MemoryMapping, error) {
		maps++
		return nil, errors.Join(syscall.ENOMEM, debt)
	}
	if _, e := f.acquire(); !errors.Is(e, syscall.EBUSY) || f.debt == nil {
		t.Fatal("lost cleanup authority", e)
	}
	debt.fail = false
	if _, e := f.acquire(); e == nil || f.debt != nil || debt.attempts != 2 {
		t.Fatal("cleanup retry", e, debt)
	}
	if _, e := f.acquire(); e == nil || maps != 1 {
		t.Fatal("admitted after uncertainty", e, maps)
	}
	survivor.m.Memory[8388608] ^= 0xff
	if len(f.files) != 0 {
		t.Fatal("image FD retained after admission stopped")
	}
}
