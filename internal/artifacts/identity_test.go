package artifacts

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/masahitojp/mariamem/internal/diagnostic"
)

func TestStartupIdentityUnchanged(t *testing.T) {
	b, err := resolve(fixture(t), "darwin-arm64", 15)
	if err != nil {
		t.Fatal(err)
	}
	build, err := b.CheckStartupIdentity(b.Runtime, b.Module)
	if err != nil || build != b.Build {
		t.Fatalf("%s %v", build, err)
	}
	// Tokens cannot be recreated from the editable Bundle fields or path alone.
	zero := Bundle{Dir: b.Dir, Runtime: b.Runtime, Module: b.Module, Build: b.Build}
	if _, err = zero.CheckStartupIdentity(zero.Runtime, zero.Module); err == nil {
		t.Fatal("unverified fields accepted")
	}
	for _, modify := range []func(*Bundle){func(b *Bundle) { b.Build = "stale" }, func(b *Bundle) { b.Module += ".other" }, func(b *Bundle) { b.Dir += ".other" }} {
		changed := b
		modify(&changed)
		if _, err = changed.CheckStartupIdentity(changed.Runtime, changed.Module); err == nil {
			t.Fatal("stale identity accepted")
		}
	}
}

func TestStartupIdentityRejectsMutation(t *testing.T) {
	for _, name := range []string{"manifest.json", "wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json"} {
		for _, kind := range []string{"write-reset-mtime", "replace", "remove", "symlink", "chmod"} {
			t.Run(name+"/"+kind, func(t *testing.T) {
				b, err := resolve(fixture(t), "darwin-arm64", 15)
				if err != nil {
					t.Fatal(err)
				}
				path := filepath.Join(b.Dir, name)
				before, err := os.Stat(path)
				if err != nil {
					t.Fatal(err)
				}
				raw, err := os.ReadFile(path)
				if err != nil {
					t.Fatal(err)
				}
				switch kind {
				case "write-reset-mtime":
					raw[0] ^= 1
					if err = os.WriteFile(path, raw, before.Mode()); err != nil {
						t.Fatal(err)
					}
					if err = os.Chtimes(path, before.ModTime(), before.ModTime()); err != nil {
						t.Fatal(err)
					}
				case "replace":
					if err = os.Rename(path, path+".old"); err != nil {
						t.Fatal(err)
					}
					if err = os.WriteFile(path, raw, before.Mode()); err != nil {
						t.Fatal(err)
					}
				case "remove":
					if err = os.Remove(path); err != nil {
						t.Fatal(err)
					}
				case "symlink":
					if err = os.Rename(path, path+".old"); err != nil {
						t.Fatal(err)
					}
					if err = os.Symlink(path+".old", path); err != nil {
						t.Fatal(err)
					}
				case "chmod":
					if err = os.Chmod(path, before.Mode()^0100); err != nil {
						t.Fatal(err)
					}
				}
				_, err = b.CheckStartupIdentity(b.Runtime, b.Module)
				var detail *diagnostic.Error
				if !errors.As(err, &detail) || detail.Code != "artifact_mismatch" || detail.Stage != "artifact_validation" {
					t.Fatalf("mutation accepted or wrong diagnostic: %v", err)
				}
			})
		}
	}
}

func TestStartupIdentitySingleOwner(t *testing.T) {
	b, err := resolve(fixture(t), "darwin-arm64", 15)
	if err != nil {
		t.Fatal(err)
	}
	if err = b.ClaimStartupIdentity(); err != nil {
		t.Fatal(err)
	}
	copy := b
	if err = copy.ClaimStartupIdentity(); err == nil {
		t.Fatal("same identity used by two startups")
	}
	if _, err = b.CheckStartupIdentity(b.Runtime, b.Module); err != nil {
		t.Fatal("owner cannot recheck", err)
	}
	// A new call fully validates even the same unchanged NativeDir.
	fresh, err := resolve(b.Dir, "darwin-arm64", 15)
	if err != nil {
		t.Fatal(err)
	}
	if err = fresh.ClaimStartupIdentity(); err != nil {
		t.Fatal(err)
	}
}
