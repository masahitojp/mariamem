package snapshot

import (
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
)

// Handoff is an internal exception for an explicitly selected different host
// executable. It is not a user persistence API. The caller owns and removes the
// fresh temporary destination after the receiver has imported private backing.
func (o *Owned) Handoff(destination, build string) (err error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	if o.closed || o.heap == nil {
		return errors.New("handoff requires a live heap baseline")
	}
	h := o.heap
	if err = h.Check(build); err != nil {
		return err
	}
	if err = os.Mkdir(destination, 0700); err != nil {
		return err
	}
	defer func() {
		if err != nil {
			_ = os.RemoveAll(destination)
		}
	}()
	root := filepath.Join(destination, "data")
	for _, n := range h.Dirs() {
		if err = os.MkdirAll(filepath.Join(root, n), 0700); err != nil {
			return err
		}
	}
	m := Manifest{Format: "mariamem-cold-snapshot", Version: 1, WASM: build, Storage: "memory", Entries: map[string]Entry{}}
	for _, n := range h.Dirs() {
		m.Entries[n] = Entry{Kind: "directory"}
	}
	for _, n := range h.Names() {
		f := h.File(n)
		size := f.Size()
		m.Entries[n] = Entry{Kind: "file", Bytes: &size, SHA256: f.Digest()}
		out, e := os.OpenFile(filepath.Join(root, n), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if e != nil {
			return e
		}
		_, e = io.Copy(out, io.NewSectionReader(f, 0, size))
		if e = errors.Join(e, out.Close()); e != nil {
			return e
		}
	}
	b, e := json.Marshal(m)
	if e != nil {
		return e
	}
	return os.WriteFile(filepath.Join(destination, "manifest.json"), b, 0600)
}
