// Package snapshot stores cold database files, never live session state.
package snapshot

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
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
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err = io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
func ModuleBuild(module string) (string, error) {
	b, err := os.ReadFile(module + ".json")
	if err != nil {
		return "", err
	}
	var m struct {
		WASM    string `json:"wasm_sha256"`
		Module  string `json:"module_sha256"`
		Version int    `json:"snapshot_version"`
	}
	if err = json.Unmarshal(b, &m); err != nil {
		return "", err
	}
	hash, err := Digest(module)
	if err != nil {
		return "", err
	}
	decoded, e := hex.DecodeString(m.WASM)
	if e != nil || len(decoded) != 32 || m.Version != 1 || hash != m.Module {
		return "", errors.New("guest artifact metadata mismatch")
	}
	return m.WASM, nil
}
func Inventory(root string) (map[string]Entry, error) {
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
		if info.IsDir() {
			result[name] = Entry{Kind: "directory"}
			return nil
		}
		if path == root || !info.Mode().IsRegular() {
			return fmt.Errorf("snapshot contains a link or special file: %s", path)
		}
		hash, err := Digest(path)
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
	for _, name := range []string{path, filepath.Join(path, "manifest.json")} {
		info, err := os.Lstat(name)
		if err != nil {
			return nil, err
		}
		if name == path && !info.IsDir() || name != path && !info.Mode().IsRegular() {
			return nil, errors.New("invalid snapshot root or manifest")
		}
	}
	children, err := os.ReadDir(path)
	if err != nil {
		return nil, err
	}
	if len(children) != 2 {
		return nil, errors.New("snapshot must contain only data and manifest.json")
	}
	b, err := os.ReadFile(filepath.Join(path, "manifest.json"))
	if err != nil {
		return nil, err
	}
	var m Manifest
	if err = json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	if m.Format != "mariamem-cold-snapshot" || m.Version != 1 || m.WASM != build || m.Storage != "memory" {
		return nil, errors.New("snapshot format or WASM build mismatch")
	}
	entries, err := Inventory(filepath.Join(path, "data"))
	if err != nil {
		return nil, err
	}
	if !reflect.DeepEqual(entries, m.Entries) {
		return nil, errors.New("snapshot file manifest mismatch")
	}
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
