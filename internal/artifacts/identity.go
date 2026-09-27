package artifacts

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sync"

	"github.com/masahitojp/mariamem/internal/diagnostic"
)

// startupIdentity is minted only after this call has verified the native bundle.
// It is not a cache: each Start hashes all required native files again.
// NativeDir must remain unchanged throughout startup. Metadata rechecks catch
// replacement and in-place mutations, including writes that restore mtime; they
// do not provide atomic exclusion against hostile concurrent writers. Wasmer
// still opens paths after validation, as it did before identity reuse.
type startupIdentity struct {
	mu          sync.Mutex
	claimed     bool
	root, build string
	files       map[string]os.FileInfo
}

func captureIdentity(root string) (*startupIdentity, error) {
	identity := &startupIdentity{root: root, files: make(map[string]os.FileInfo)}
	for _, name := range []string{"manifest.json", "wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json"} {
		info, err := os.Lstat(filepath.Join(root, name))
		if err != nil {
			return nil, err
		}
		if !info.Mode().IsRegular() {
			return nil, fmt.Errorf("artifact must be a regular file: %s", name)
		}
		if changeTime(info) == nil {
			return nil, fmt.Errorf("cannot establish artifact change identity: %s", name)
		}
		identity.files[name] = info
	}
	return identity, nil
}

// Both supported systems expose inode change time, independently of mtime.
// Reflection keeps the startup identity portable across Go's Stat_t definitions.
func changeTime(info os.FileInfo) any {
	value := reflect.ValueOf(info.Sys())
	if value.Kind() == reflect.Pointer {
		value = value.Elem()
	}
	if value.Kind() != reflect.Struct {
		return nil
	}
	for _, name := range []string{"Ctim", "Ctimespec"} {
		field := value.FieldByName(name)
		if field.IsValid() && field.CanInterface() {
			return field.Interface()
		}
	}
	return nil
}

// CheckStartupIdentity can only reuse the exact bundle this call validated.
// Call again directly before process launch, after snapshot validation.
func (b Bundle) CheckStartupIdentity(runtime, module string) (string, error) {
	fail := func(err error) (string, error) {
		return "", diagnostic.Wrap("artifact_mismatch", "artifact_validation", fmt.Errorf("native bundle changed or has no verified startup identity; re-extract a complete matching bundle and keep NativeDir unchanged during startup: %w", err))
	}
	identity := b.verified
	if identity == nil || b.Dir != identity.root || b.Build != identity.build || runtime != filepath.Join(identity.root, "wasmer-headless") || module != filepath.Join(identity.root, "mariamem.wasmu") {
		return fail(fmt.Errorf("stale or mismatched startup identity"))
	}
	for name, before := range identity.files {
		after, err := os.Lstat(filepath.Join(identity.root, name))
		if err != nil {
			return fail(err)
		}
		if !after.Mode().IsRegular() || !os.SameFile(before, after) || before.Size() != after.Size() || before.Mode() != after.Mode() || !before.ModTime().Equal(after.ModTime()) || !reflect.DeepEqual(changeTime(before), changeTime(after)) {
			return fail(fmt.Errorf("artifact mutated after validation: %s", name))
		}
	}
	return identity.build, nil
}

// ClaimStartupIdentity transfers a verified bundle to exactly one host startup.
// Rechecking the owned identity is allowed, reusing it for another Start is not.
func (b Bundle) ClaimStartupIdentity() error {
	if b.verified == nil {
		_, err := b.CheckStartupIdentity(b.Runtime, b.Module)
		return err
	}
	b.verified.mu.Lock()
	defer b.verified.mu.Unlock()
	if b.verified.claimed {
		return diagnostic.Wrap("artifact_mismatch", "artifact_validation", fmt.Errorf("verified artifact identity was already consumed by a startup; validate the native bundle again"))
	}
	if _, err := b.CheckStartupIdentity(b.Runtime, b.Module); err != nil {
		return err
	}
	b.verified.claimed = true
	return nil
}
