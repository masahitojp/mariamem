package snapshot

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/masahitojp/mariamem/internal/timing"
	"io"
	"os"
	"path/filepath"

	"github.com/masahitojp/mariamem/internal/prepared"
)

// OwnRoot accepts only a sealed capture-produced resource, never raw bytes.
// The process's Capture checks the request/source binding before this call.
func OwnRoot(r *prepared.Root, build string) (*Owned, error) {
	_, finish := timing.Begin(context.Background(), "snapshot_own")
	defer finish()
	if e := r.Check(build); e != nil {
		return nil, e
	}
	return &Owned{root: r}, nil
}

// caller holds o.mu. Payload is streamed once at this copy/serialization boundary.
func (o *Owned) handoffRoot(destination, build string) (err error) {
	r := o.root
	if e := r.Check(build); e != nil {
		return e
	}
	if err = os.Mkdir(destination, 0700); err != nil {
		return err
	}
	defer func() {
		if err != nil {
			_ = os.RemoveAll(destination)
		}
	}()
	data := filepath.Join(destination, "data")
	m := Manifest{Format: "mariamem-cold-snapshot", Version: 1, WASM: build, Storage: "memory", Entries: map[string]Entry{}}
	for _, n := range r.Dirs() {
		if err = os.MkdirAll(filepath.Join(data, n), 0700); err != nil {
			return err
		}
		m.Entries[n] = Entry{Kind: "directory"}
	}
	for _, n := range r.Names() {
		f := r.File(n)
		size := f.Size()
		out, e := os.OpenFile(filepath.Join(data, n), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if e != nil {
			return e
		}
		sum := sha256.New()
		_, e = io.Copy(io.MultiWriter(out, sum), io.NewSectionReader(f, 0, size))
		e = errors.Join(e, out.Close())
		if e != nil {
			return e
		}
		m.Entries[n] = Entry{Kind: "file", Bytes: &size, SHA256: hex.EncodeToString(sum.Sum(nil))}
	}
	p, e := json.Marshal(m)
	if e != nil {
		return e
	}
	return os.WriteFile(filepath.Join(destination, "manifest.json"), p, 0600)
}
