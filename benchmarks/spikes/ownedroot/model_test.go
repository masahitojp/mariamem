package ownedroot

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"runtime"
	"strings"
	"sync"
	"testing"
	"weak"

	stored "github.com/masahitojp/mariamem/internal/snapshot"
)

func must(t *testing.T, e error) {
	t.Helper()
	if e != nil {
		t.Fatal(e)
	}
}
func open(t *testing.T, b *Builder, n string) *Handle {
	t.Helper()
	h, e := b.Open(n)
	must(t, e)
	return h
}
func own(t *testing.T, b *Builder) *Owner {
	t.Helper()
	c, e := b.Request()
	must(t, e)
	must(t, b.Freeze(c, -1))
	o, e := c.Acquire("guest", b.meter)
	must(t, e)
	return o
}
func digest(p []byte) string { return fmt.Sprintf("%x", sha256.Sum256(p)) }
func evidence(t *testing.T, name string, v any) {
	t.Helper()
	p, e := json.Marshal(map[string]any{"name": name, "value": v})
	must(t, e)
	t.Log("EVIDENCE " + string(p))
}
func payload(c Counts) int64 {
	return c.ReadBytes + c.CopyBytes + c.HashBytes + c.ZeroBytes + c.WriteBytes + c.AllocBytes
}
func assertNoCapturePayload(t *testing.T, m *Meter) {
	t.Helper()
	for k, c := range m.Snapshot() {
		if strings.HasPrefix(k, "freeze/") || strings.HasPrefix(k, "acquire/") {
			if payload(c) != 0 {
				t.Fatalf("capture touched payload: %s %+v", k, c)
			}
		}
	}
}
func assertBytes(t *testing.T, r interface {
	ReadAt(string, []byte, int64) (int, error)
}, name string, want []byte) {
	t.Helper()
	p := bytes.Repeat([]byte{0xff}, len(want)+1)
	n, e := r.ReadAt(name, p, 0)
	if n != len(want) || e != io.EOF || !bytes.Equal(p[:n], want) {
		t.Fatalf("content/EOF n=%d want=%d err=%v", n, len(want), e)
	}
}
func TestRoutesAndPositiveControls(t *testing.T) {
	for _, route := range []string{"dirty", "inherited", "zero", "mixed"} {
		t.Run(route, func(t *testing.T) {
			m := NewMeter()
			b := New("guest", m)
			h := open(t, b, "dir/data")
			size := int64(3*BlockSize + 3)
			must(t, h.Truncate(size))
			if route != "zero" {
				must(t, h.WriteAt([]byte("abc"), BlockSize-1))
			}
			if route == "dirty" {
				must(t, h.WriteAt(bytes.Repeat([]byte{7}, int(size)), 0))
			}
			h.Close()
			if route == "inherited" || route == "mixed" {
				p := own(t, b)
				var e error
				b, e = p.Fork("guest")
				must(t, e)
				p.Close()
				if route == "mixed" {
					h = open(t, b, "dir/data")
					must(t, h.WriteAt([]byte{9}, 2*BlockSize))
					h.Close()
				}
			}
			o := own(t, b)
			defer o.Close()
			assertNoCapturePayload(t, m)
			p := make([]byte, size)
			_, e := o.ReadAt("dir/data", p, 0)
			must(t, e)
			must(t, o.VerifyContents("guest", map[string]string{"dir/data": digest(p)}))
			v := m.Snapshot()
			var r, z, hs int64
			for k, c := range v {
				if strings.HasPrefix(k, "application-read/") {
					r += c.ReadBytes
					z += c.ZeroBytes
				}
				if strings.HasPrefix(k, "strict/") {
					hs += c.HashBytes
				}
			}
			if r+z != size || hs != size {
				t.Fatalf("counter control failed read=%d zero=%d hash=%d", r, z, hs)
			}
			evidence(t, "routes/"+route, v)
		})
	}
}

func TestReferenceAndGenerations(t *testing.T) {
	for _, seed := range []int64{1, 73, 991} {
		t.Run(fmt.Sprint(seed), func(t *testing.T) {
			m := NewMeter()
			b := New("guest", m)
			h := open(t, b, "f")
			rng := rand.New(rand.NewSource(seed))
			ref := []byte{}
			for step := 0; step < 500; step++ {
				off := rng.Intn(5 * BlockSize)
				n := rng.Intn(BlockSize + 5)
				switch rng.Intn(4) {
				case 0:
					p := make([]byte, n)
					rng.Read(p)
					must(t, h.WriteAt(p, int64(off)))
					if n > 0 {
						if off+n > len(ref) {
							ref = append(ref, make([]byte, off+n-len(ref))...)
						}
						copy(ref[off:], p)
					}
				case 1:
					must(t, h.Truncate(int64(off)))
					if off < len(ref) {
						ref = append([]byte(nil), ref[:off]...)
					} else {
						ref = append(ref, make([]byte, off-len(ref))...)
					}
				case 2:
					must(t, h.Allocate(int64(off)))
					if off > len(ref) {
						ref = append(ref, make([]byte, off-len(ref))...)
					}
				case 3:
					p := []byte{byte(step)}
					must(t, h.Append(p))
					ref = append(ref, p...)
				}
				assertBytes(t, b, "f", ref)
				if step%25 == 24 {
					h.Close()
					p := own(t, b)
					must(t, p.VerifyContents("guest", map[string]string{"f": digest(ref)}))
					var e error
					b, e = p.Fork("guest")
					must(t, e)
					p.Close()
					h = open(t, b, "f")
					// The fork root has no ancestor-root link; only flat block references.
					for _, f := range b.r.files {
						for _, e := range f.blocks {
							if e.writable {
								t.Fatal("inherited block writable")
							}
						}
					}
				}
			}
			h.Close()
			o := own(t, b)
			defer o.Close()
			assertBytes(t, o, "f", ref)
			assertNoCapturePayload(t, m)
			evidence(t, "reference/"+fmt.Sprint(seed), map[string]int{"operations": 500, "generations": 20})
		})
	}
}

func TestOldWritersAliasesAndMetadata(t *testing.T) {
	m := NewMeter()
	b := New("guest", m)
	h := open(t, b, "dir/f")
	alias := []byte("before")
	must(t, h.WriteAt(alias, 0))
	alias[0] = 'X'
	rel, e := b.OpenRelative("dir", "f")
	must(t, e)
	must(t, b.Rename("dir/f", "dir/g"))
	o := own(t, b)
	defer o.Close()
	for n, fn := range map[string]func() error{
		"write": func() error { return h.WriteAt([]byte{9}, 0) }, "append": func() error { return h.Append([]byte{9}) },
		"truncate": func() error { return h.Truncate(0) }, "relative-truncate": func() error { return rel.Truncate(0) },
		"allocate": func() error { return h.Allocate(99) }, "rename": func() error { return b.Rename("dir/g", "dir/z") },
		"remove": func() error { return b.Remove("dir/g") }, "new-file": func() error { _, e := b.Open("new"); return e },
	} {
		if fn() == nil {
			t.Fatalf("old operation accepted: %s", n)
		}
	}
	h.Close()
	rel.Close()
	assertBytes(t, o, "dir/g", []byte("before"))
	if _, e = o.ReadAt("dir/f", make([]byte, 1), 0); e == nil {
		t.Fatal("old name retained")
	}
	left, e := o.Fork("guest")
	must(t, e)
	right, e := o.Fork("guest")
	must(t, e)
	o.Close()
	l := open(t, left, "dir/g")
	must(t, l.Truncate(2))
	must(t, l.Truncate(20))
	must(t, l.WriteAt([]byte("after"), 8))
	l.Close()
	assertBytes(t, right, "dir/g", []byte("before"))
	next := own(t, left)
	defer next.Close()
	want := make([]byte, 20)
	copy(want, "be")
	copy(want[8:], "after")
	assertBytes(t, next, "dir/g", want)
	_, e = o.Fork("guest")
	if e == nil {
		t.Fatal("closed baseline accepted fork")
	}
	evidence(t, "writer-isolation", map[string]any{"old_writer_rejections": 8, "input_alias_detached": true, "sibling_and_child_after_parent_close": true})
}

func TestSubstitutionAndStateOracles(t *testing.T) {
	for _, kind := range []string{"other-root", "unsealed", "other-capture", "identity", "abandoned", "missing-file", "extra-file", "block", "size", "directory"} {
		t.Run(kind, func(t *testing.T) {
			m := NewMeter()
			b := New("guest", m)
			h := open(t, b, "f")
			must(t, h.WriteAt([]byte("original"), 0))
			h.Close()
			c, e := b.Request()
			must(t, e)
			must(t, b.Freeze(c, -1))
			switch kind {
			case "other-root":
				x := New("guest", m)
				open(t, x, "f").Close()
				other := own(t, x)
				c.result = other.r
			case "unsealed":
				c.result.sealed = false
			case "other-capture":
				c.key = &captureKey{2}
			case "identity":
				c.result.build = "other"
			case "abandoned":
				c.Discard()
			case "missing-file":
				delete(c.result.files, "f")
			case "extra-file":
				c.result.files["extra"] = &file{blocks: map[int64]entry{}}
			case "block":
				f := c.result.files["f"]
				e := f.blocks[0]
				e.block = new(block)
				f.blocks[0] = e
			case "size":
				c.result.files["f"].size++
			case "directory":
				c.result.dirs["extra"] = true
			}
			o, e := c.Acquire("guest", m)
			if e == nil || o != nil {
				t.Fatalf("substitution accepted: %s", kind)
			}
			c.Discard()
			if c.result != nil || c.expected != nil {
				t.Fatal("discard retained root")
			}
			assertNoCapturePayload(t, m)
		})
	}
	// The result cannot be consumed twice or acquired before Freeze.
	m := NewMeter()
	b := New("guest", m)
	c, e := b.Request()
	must(t, e)
	if o, e := c.Acquire("guest", m); e == nil || o != nil {
		t.Fatal("uncompleted accepted")
	}
	must(t, b.Freeze(c, -1))
	o, e := c.Acquire("guest", m)
	must(t, e)
	defer o.Close()
	if x, e := c.Acquire("guest", m); e == nil || x != nil {
		t.Fatal("replayed capture")
	}
	evidence(t, "capture-rejections", map[string]int{"cases": 12})
}

// Keep this independent strict oracle at the owner layer. Do not interpret the
// no-hash acquisition's acceptance below as equivalent integrity verification.
func TestStrictOracleAndInternalCorruptionLimit(t *testing.T) {
	m := NewMeter()
	b := New("guest", m)
	h := open(t, b, "f")
	must(t, h.WriteAt([]byte("original"), 0))
	h.Close()
	c, e := b.Request()
	must(t, e)
	must(t, b.Freeze(c, -1))
	c.result.files["f"].blocks[0].block.data[0] ^= 255 // Deliberately bypass all APIs.
	o, e := c.Acquire("guest", m)
	must(t, e)
	defer o.Close()
	if o.VerifyContents("guest", map[string]string{"f": digest([]byte("original"))}) == nil {
		t.Fatal("strict corruption oracle failed")
	}
	evidence(t, "internal-corruption-limit", map[string]string{"ownership_acquire": "NOT DETECTED", "strict_oracle": "REJECTED", "interpretation": "Known detection difference; not product approval"})
}

func TestFailureAbandonmentAndWeakLifetime(t *testing.T) {
	for _, after := range []int{0, 1} {
		b := New("guest", NewMeter())
		h := open(t, b, "a")
		must(t, h.WriteAt([]byte{1}, 0))
		h.Close()
		open(t, b, "b").Close()
		c, e := b.Request()
		must(t, e)
		ref := weak.Make(b.r)
		if b.Freeze(c, after) == nil {
			t.Fatal("injected failure hidden")
		}
		if c.expected != nil || c.result != nil || b.r != nil {
			t.Fatal("failed state retained root")
		}
		runtime.GC()
		if ref.Value() != nil {
			t.Fatal("failed root live")
		}
		runtime.KeepAlive(c)
		runtime.KeepAlive(b)
	}
	b := New("guest", NewMeter())
	c, e := b.Request()
	must(t, e)
	c.Discard()
	if b.Freeze(c, -1) == nil {
		t.Fatal("abandoned freeze accepted")
	}
	// Discard before freeze does not consume the mutable data in this component.
	h := open(t, b, "still-mutable")
	h.Close()
	b = New("guest", NewMeter())
	h = open(t, b, "f")
	must(t, h.WriteAt([]byte{1}, 0))
	h.Close()
	c, e = b.Request()
	must(t, e)
	must(t, b.Freeze(c, -1))
	ref := weak.Make(c.result)
	o, e := c.Acquire("guest", b.meter)
	must(t, e)
	if c.expected != nil || c.result != nil {
		t.Fatal("transport retains acquired root")
	}
	child, e := o.Fork("guest")
	must(t, e)
	o.Close()
	runtime.GC()
	if ref.Value() != nil {
		t.Fatal("child retained parent root")
	}
	assertBytes(t, child, "f", []byte{1})
	runtime.KeepAlive(child)
	runtime.KeepAlive(c)
	runtime.KeepAlive(o)
	runtime.KeepAlive(b)
	evidence(t, "lifetime", map[string]bool{"failed_root_released": true, "transport_released": true, "child_does_not_retain_parent_root": true})
}

func TestConcurrentForkAndClose(t *testing.T) {
	m := NewMeter()
	b := New("guest", m)
	h := open(t, b, "f")
	must(t, h.WriteAt([]byte("base"), 0))
	h.Close()
	o := own(t, b)
	var wg sync.WaitGroup
	ready := make(chan struct{}, 4)
	release := make(chan struct{})
	errs := make(chan error, 4)
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			child, e := o.Fork("guest")
			if e != nil {
				errs <- e
				return
			}
			ready <- struct{}{}
			<-release
			h, e := child.Open("f")
			if e != nil {
				errs <- e
				return
			}
			if e = h.WriteAt([]byte{byte(i + 1)}, 0); e != nil {
				errs <- e
			}
			h.Close()
			p := make([]byte, 4)
			_, e = child.ReadAt("f", p, 0)
			if e != nil || p[0] != byte(i+1) || string(p[1:]) != "ase" {
				errs <- fmt.Errorf("child isolation %v %v", p, e)
			}
		}(i)
	}
	for i := 0; i < 4; i++ {
		<-ready
	}
	o.Close()
	close(release)
	wg.Wait()
	close(errs)
	for e := range errs {
		must(t, e)
	}
	evidence(t, "concurrent", map[string]int{"independent_children_after_close": 4})
}

func TestHandoffManifestAndCorruption(t *testing.T) {
	m := NewMeter()
	b := New("guest", m)
	h := open(t, b, "dir/f")
	must(t, h.WriteAt([]byte("abc"), 0))
	must(t, h.Truncate(BlockSize+3))
	h.Close()
	o := own(t, b)
	defer o.Close()
	tr, e := o.Export()
	must(t, e)
	encoded, e := json.Marshal(tr)
	must(t, e)
	var existing stored.Manifest
	dec := json.NewDecoder(bytes.NewReader(encoded))
	dec.DisallowUnknownFields()
	must(t, dec.Decode(&existing))
	if existing.WASM != "guest" || existing.Storage != "memory" || existing.Version != 1 || existing.Entries["dir/f"].SHA256 == "" {
		t.Fatal("existing manifest mismatch")
	}
	x, e := Import(tr, "guest", m)
	must(t, e)
	defer x.Close()
	want := make([]byte, BlockSize+3)
	copy(want, "abc")
	assertBytes(t, x, "dir/f", want)
	if p, e := Import(tr, "other", m); e == nil || p != nil {
		t.Fatal("wrong guest accepted")
	}
	tr.Data["dir/f"][0] ^= 255
	if p, e := Import(tr, "guest", m); e == nil || p != nil {
		t.Fatal("corrupt transfer accepted")
	}
	assertBytes(t, x, "dir/f", want)
	var send, receive, copyBytes int64
	for k, c := range m.Snapshot() {
		if strings.HasPrefix(k, "handoff-send/") {
			send += c.HashBytes
		}
		if strings.HasPrefix(k, "handoff-receive/") {
			receive += c.HashBytes
		}
		if strings.HasPrefix(k, "handoff-copy/") {
			copyBytes += c.CopyBytes
		}
	}
	if send == 0 || receive == 0 || copyBytes == 0 {
		t.Fatal("handoff counters failed")
	}
	evidence(t, "handoff", m.Snapshot())
}

func TestWriteAndMetadataCostSeparation(t *testing.T) {
	m := NewMeter()
	b := New("guest", m)
	h := open(t, b, "f")
	must(t, h.Truncate(100*1024*1024))
	must(t, h.WriteAt([]byte{1}, 0))
	h.Close()
	o := own(t, b)
	defer o.Close()
	child, e := o.Fork("guest")
	must(t, e)
	h = open(t, child, "f")
	before := m.Snapshot()["write/inherited"].CopyBytes
	must(t, h.WriteAt([]byte{2}, 1))
	h.Close()
	delta := m.Snapshot()["write/inherited"].CopyBytes - before
	if delta != 1 {
		t.Fatalf("copy should only preserve valid prefix in this fixture: %d", delta)
	}
	if len(child.r.files["f"].blocks) != 1 {
		t.Fatal("zero reservation materialized")
	}
	next := own(t, child)
	defer next.Close()
	assertNoCapturePayload(t, m)
	evidence(t, "cost", map[string]any{"logical_bytes": 100 * 1024 * 1024, "materialized_blocks": 1, "cow_preserved_bytes": delta, "parent_root_depth": 0, "metrics": m.Snapshot()})
}
