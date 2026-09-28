// Package snapshot stores cold database files, never live session state.
package snapshot

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/timing"
	"io"
	"os"
	"path/filepath"
	"reflect"
)

type Entry struct {
	Kind   string `json:"kind"`
	Bytes  *int64 `json:"bytes,omitempty"`
	SHA256 string `json:"sha256,omitempty"`
}
type Manifest struct {
	Format  string           `json:"format"`
	Version int              `json:"version"`
	WASM    string           `json:"wasm_sha256"`
	Storage string           `json:"source_storage"`
	Entries map[string]Entry `json:"entries"`
}

func Digest(path string) (string, error) {
	return DigestTimed(context.Background(), path, "digest")
}

// DigestTimed splits open, read/hash and close without changing digest semantics.
func DigestTimed(ctx context.Context, path, label string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	timing.Work(ctx, label+"/opened", 0, 1)
	defer func() { f.Close(); timing.Mark(ctx, label+"/closed") }()
	h := sha256.New()
	n, err := io.Copy(h, f)
	timing.Work(ctx, label+"/read_hashed", n, 0)
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
func ModuleBuild(module string) (string, error) {
	hash, err := Digest(module)
	if err != nil {
		return "", err
	}
	return ModuleBuildWithDigest(module, hash)
}

// ModuleBuildWithDigest validates the sidecar against a digest just verified by
// the caller in this startup call. It does not establish trust in a path.
func ModuleBuildWithDigest(module, hash string) (string, error) {
	return ModuleBuildWithDigestTimed(context.Background(), module, hash)
}
func ModuleBuildWithDigestTimed(ctx context.Context, module, hash string) (string, error) {
	b, err := os.ReadFile(module + ".json")
	if err != nil {
		return "", err
	}
	timing.Work(ctx, "sidecar_read", int64(len(b)), 1)
	var m struct {
		WASM    string `json:"wasm_sha256"`
		Module  string `json:"module_sha256"`
		Version int    `json:"snapshot_version"`
	}
	if err = json.Unmarshal(b, &m); err != nil {
		return "", err
	}
	decoded, e := hex.DecodeString(m.WASM)
	verified, hashErr := hex.DecodeString(hash)
	if e != nil || len(decoded) != 32 || hashErr != nil || len(verified) != 32 || m.Version != 1 || hash != m.Module {
		return "", errors.New("guest artifact metadata mismatch")
	}
	return m.WASM, nil
}
func Inventory(root string) (map[string]Entry, error) {
	return inventory(context.Background(), root)
}
func inventory(ctx context.Context, root string) (map[string]Entry, error) {
	result := make(map[string]Entry)
	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		name, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		name = filepath.ToSlash(name)
		timing.Work(ctx, "inventory/"+name+"/metadata", 0, 1)
		if info.IsDir() {
			result[name] = Entry{Kind: "directory"}
			return nil
		}
		if path == root || !info.Mode().IsRegular() {
			return fmt.Errorf("snapshot contains a link or special file: %s", path)
		}
		hash, err := DigestTimed(ctx, path, "inventory/"+name)
		if err != nil {
			return err
		}
		size := info.Size()
		result[name] = Entry{Kind: "file", Bytes: &size, SHA256: hash}
		return nil
	})
	return result, err
}
func Validate(path, build string) (*Manifest, error) {
	return ValidateTimed(context.Background(), path, build)
}
func ValidateTimed(ctx context.Context, path, build string) (*Manifest, error) {
	ctx, finish := timing.Begin(ctx, "snapshot_verification")
	defer finish()
	for _, name := range []string{path, filepath.Join(path, "manifest.json")} {
		info, err := os.Lstat(name)
		if err != nil {
			return nil, err
		}
		if name == path && !info.IsDir() || name != path && !info.Mode().IsRegular() {
			return nil, errors.New("invalid snapshot root or manifest")
		}
	}
	timing.Work(ctx, "root_metadata_checked", 0, 2)
	children, err := os.ReadDir(path)
	if err != nil {
		return nil, err
	}
	if len(children) != 2 {
		return nil, errors.New("snapshot must contain only data and manifest.json")
	}
	timing.Work(ctx, "root_inventory_checked", 0, int64(len(children)))
	b, err := os.ReadFile(filepath.Join(path, "manifest.json"))
	if err != nil {
		return nil, err
	}
	timing.Work(ctx, "manifest_read", int64(len(b)), 1)
	var m Manifest
	if err = json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	if m.Format != "mariamem-cold-snapshot" || m.Version != 1 || m.WASM != build || m.Storage != "memory" {
		return nil, errors.New("snapshot format or WASM build mismatch")
	}
	timing.Mark(ctx, "manifest_identity_checked")
	entries, err := inventory(ctx, filepath.Join(path, "data"))
	if err != nil {
		return nil, err
	}
	timing.Mark(ctx, "inventory_complete")
	if !reflect.DeepEqual(entries, m.Entries) {
		return nil, errors.New("snapshot file manifest mismatch")
	}
	timing.Mark(ctx, "inventory_compared")
	return &m, nil
}
func Publish(transfer, destination, build string) error {
	source := filepath.Join(transfer, "data")
	entries, err := Inventory(source)
	if err != nil {
		return err
	}
	target := filepath.Join(destination, "data")
	err = filepath.WalkDir(source, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		name, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		out := filepath.Join(target, name)
		if d.IsDir() {
			return os.Mkdir(out, 0700)
		}
		if !d.Type().IsRegular() {
			return errors.New("invalid exported file")
		}
		in, err := os.Open(path)
		if err != nil {
			return err
		}
		defer in.Close()
		f, err := os.OpenFile(out, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if err != nil {
			return err
		}
		_, err = io.Copy(f, in)
		return errors.Join(err, f.Close())
	})
	if err != nil {
		return err
	}
	copied, err := Inventory(target)
	if err != nil {
		return err
	}
	if !reflect.DeepEqual(entries, copied) {
		return errors.New("snapshot copy mismatch")
	}
	m := Manifest{Format: "mariamem-cold-snapshot", Version: 1, WASM: build, Storage: "memory", Entries: entries}
	b, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	pending := filepath.Join(destination, "manifest.pending")
	if err = os.WriteFile(pending, append(b, '\n'), 0600); err != nil {
		return err
	}
	return os.Rename(pending, filepath.Join(destination, "manifest.json"))
}
