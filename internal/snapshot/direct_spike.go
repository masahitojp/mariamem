package snapshot

// Experimental temporary-Snapshot route. Not an adopted production interface.
// Source bytes are stable after guest join; destination is a private empty
// directory. Materialization does NOT by itself confer verified ownership:
// the caller must subsequently AdoptCreated and retain its exact descriptors.
import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"io/fs"
	"os"
	"path/filepath"

	"github.com/masahitojp/mariamem/internal/timing"
)

// DirectRequest is private experiment coordination inside the host-owned
// transfer directory. A request is installed only after Snapshot preconditions.
const DirectRequest = ".direct-snapshot-request"

func MaterializeDirect(source fs.FS, destination, build string) error {
	ctx, finish := timing.Begin(context.Background(), "snapshot_direct_materialize")
	defer finish()
	buffer := make([]byte, 128*1024)
	return materializeDirect(source, destination, build, func(w io.Writer, r io.Reader) (int64, error) {
		n, err := io.CopyBuffer(w, r, buffer)
		timing.Work(ctx, "source_hashed_and_materialized", n, 1)
		return n, err
	})
}

func materializeDirect(source fs.FS, destination, build string, copyBytes func(io.Writer, io.Reader) (int64, error)) (err error) {
	children, err := os.ReadDir(destination)
	if err != nil {
		return err
	}
	if len(children) != 0 {
		return errors.New("direct snapshot requires empty private destination")
	}
	defer func() {
		if err != nil {
			err = errors.Join(err, os.RemoveAll(destination))
		}
	}()
	entries := map[string]Entry{}
	err = fs.WalkDir(source, ".", func(name string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		info, e := d.Info()
		if e != nil {
			return e
		}
		outpath := filepath.Join(destination, "data", filepath.FromSlash(name))
		if info.IsDir() {
			entries[name] = Entry{Kind: "directory"}
			return os.Mkdir(outpath, 0700)
		}
		if !info.Mode().IsRegular() {
			return errors.New("invalid direct snapshot source")
		}
		in, e := source.Open(name)
		if e != nil {
			return e
		}
		defer in.Close()
		out, e := os.OpenFile(outpath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if e != nil {
			return e
		}
		h := sha256.New()
		// Hash source bytes during their only materialization. Final ownership
		// verification must reread actual destination bytes against this digest.
		n, e := copyBytes(io.MultiWriter(out, h), in)
		e = errors.Join(e, out.Close())
		if e != nil {
			return e
		}
		if n != info.Size() {
			return errors.New("direct snapshot source size changed or short copy")
		}
		entries[name] = Entry{Kind: "file", Bytes: &n, SHA256: hex.EncodeToString(h.Sum(nil))}
		return nil
	})
	if err != nil {
		return err
	}
	m := Manifest{Format: "mariamem-cold-snapshot", Version: 1, WASM: build, Storage: "memory", Entries: entries}
	if err = checkManifest(m, build); err != nil {
		return err
	}
	b, err := json.Marshal(m)
	if err != nil {
		return err
	}
	// An internal expected-content record only. The public call cannot return
	// success until AdoptCreated verifies retained, read-only, unlinked files.
	pending := filepath.Join(destination, "manifest.pending")
	if err = os.WriteFile(pending, b, 0600); err != nil {
		return err
	}
	return os.Rename(pending, filepath.Join(destination, "manifest.json"))
}
