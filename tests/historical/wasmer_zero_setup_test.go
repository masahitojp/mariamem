//go:build historical_wasmer

// External consumer acceptance. The tagged module and real bundle are private
// fixtures, never a GitHub release. Only HTTP transport is redirected locally;
// the production resolver selects its canonical URLs and module build identity.
package historical

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"runtime/debug"
	"strings"
	"sync"
	"testing"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

type fixture struct {
	Tag             string `json:"tag"`
	Target          string `json:"target"`
	Asset           string `json:"asset"`
	ArchiveSHA      string `json:"archive_sha256"`
	SumsSHA         string `json:"sums_sha256"`
	WrongArchiveSHA string `json:"wrong_archive_sha256"`
	WrongSumsSHA    string `json:"wrong_sums_sha256"`
}
type localTransport struct {
	destination *url.URL
	base        http.RoundTripper
}

func (l localTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	if request.URL.Scheme != "https" || (request.URL.Host != "github.com" && request.URL.Host != "api.github.com") {
		return nil, fmt.Errorf("unexpected resolver URL %s", request.URL)
	}
	copied := request.Clone(request.Context())
	address := *request.URL
	address.Scheme = l.destination.Scheme
	address.Host = l.destination.Host
	copied.URL = &address
	copied.Host = l.destination.Host
	return l.base.RoundTrip(copied)
}
func must(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatal(err)
	}
}
func TestZeroSetup(t *testing.T) {
	// This fixture tests the explicit legacy downloader; default no longer downloads.
	t.Setenv("MARIAMEM_RUNTIME", "wasmer")
	root := os.Getenv("ZERO_FIXTURE")
	if root == "" {
		t.Skip("run via run_zero_setup.py; no default network")
	}
	raw, err := os.ReadFile(filepath.Join(root, "fixture.json"))
	must(t, err)
	var f fixture
	must(t, json.Unmarshal(raw, &f))
	info, ok := debug.ReadBuildInfo()
	if !ok {
		t.Fatal("build info missing")
	}
	found := false
	for _, m := range info.Deps {
		if m.Path == "github.com/masahitojp/mariamem" {
			if m.Version != f.Tag || m.Replace != nil {
				t.Fatalf("not the exact tagged fixture: %+v", m)
			}
			found = true
		}
	}
	if !found {
		t.Fatal("fixture module identity missing")
	}
	var mu sync.Mutex
	offline, corrupt, interrupt, absent, wrongVersion := false, false, false, false, false
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		requests++
		isOffline, isCorrupt, isInterrupt, isAbsent, isWrong := offline, corrupt, interrupt, absent, wrongVersion
		mu.Unlock()
		if isOffline {
			http.Error(w, "fixture offline", 503)
			return
		}
		if isAbsent {
			http.NotFound(w, r)
			return
		}
		archiveSHA, sumsSHA, servingRoot := f.ArchiveSHA, f.SumsSHA, root
		if isWrong {
			archiveSHA, sumsSHA, servingRoot = f.WrongArchiveSHA, f.WrongSumsSHA, filepath.Join(root, "incompatible")
		}
		prefix := "/masahitojp/mariamem/releases/download/" + f.Tag + "/"
		switch r.URL.Path {
		case "/repos/masahitojp/mariamem/releases/tags/" + f.Tag:
			assets := []map[string]string{{"name": f.Asset, "browser_download_url": "https://github.com" + prefix + f.Asset, "digest": "sha256:" + archiveSHA}, {"name": "SHA256SUMS", "browser_download_url": "https://github.com" + prefix + "SHA256SUMS", "digest": "sha256:" + sumsSHA}}
			mustJSON(w, map[string]any{"tag_name": f.Tag, "draft": false, "assets": assets})
		case prefix + "SHA256SUMS":
			http.ServeFile(w, r, filepath.Join(servingRoot, "SHA256SUMS"))
		case prefix + f.Asset:
			if isCorrupt {
				io.WriteString(w, "corrupted archive")
				return
			}
			if isInterrupt {
				h, ok := w.(http.Hijacker)
				if !ok {
					http.Error(w, "no hijack", 500)
					return
				}
				conn, _, err := h.Hijack()
				if err == nil {
					conn.Write([]byte("HTTP/1.1 200 OK\r\nContent-Length: 99999999\r\n\r\npartial"))
					conn.Close()
				}
				return
			}
			http.ServeFile(w, r, filepath.Join(servingRoot, f.Asset))
		default:
			http.Error(w, "unexpected fixture path", 400)
		}
	}))
	defer server.Close()
	localURL, err := url.Parse(server.URL)
	must(t, err)
	original := http.DefaultTransport
	http.DefaultTransport = localTransport{localURL, original}
	defer func() { http.DefaultTransport = original }()
	t.Setenv("MARIAMEM_NATIVE_DIR", "")
	newCache := func() string {
		cache := t.TempDir()
		t.Setenv("XDG_CACHE_HOME", cache)
		t.Setenv("HOME", cache)
		return cache
	}
	// os.UserCacheDir uses HOME/Library/Caches on macOS, XDG_CACHE_HOME on Linux.
	calls := func() int { mu.Lock(); defer mu.Unlock(); return requests }
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	start := func(t *testing.T, opts mariamem.Options) *mariamem.Database {
		db, err := mariamem.Start(ctx, opts)
		must(t, err)
		return db
	}
	closeDB := func(t *testing.T, db *mariamem.Database) { must(t, db.Close()) }
	sqlCheck := func(t *testing.T, db *mariamem.Database) {
		pool, err := sql.Open("mysql", db.DSN())
		must(t, err)
		defer pool.Close()
		var n int
		must(t, pool.QueryRowContext(ctx, "SELECT 1").Scan(&n))
		if n != 1 {
			t.Fatal(n)
		}
	}
	outcomes := map[string]string{}
	t.Run("default-generated-go-no-download", func(t *testing.T) {
		t.Setenv("MARIAMEM_RUNTIME", "")
		t.Setenv("PATH", t.TempDir())
		cache := newCache()
		before := calls()
		db := start(t, mariamem.Options{})
		defer closeDB(t, db)
		sqlCheck(t, db)
		if calls() != before {
			t.Fatal("default selected native downloader")
		}
		if files, err := os.ReadDir(cache); err != nil || len(files) != 0 {
			t.Fatal("default populated cache", err)
		}
		outcomes[t.Name()] = "PASS"
	})
	t.Run("first-download", func(t *testing.T) {
		newCache()
		db := start(t, mariamem.Options{})
		defer closeDB(t, db)
		sqlCheck(t, db)
		if calls() != 3 {
			t.Fatal(calls())
		}
		outcomes[t.Name()] = "PASS"
	})
	t.Run("cached-offline", func(t *testing.T) {
		before := calls()
		mu.Lock()
		offline = true
		mu.Unlock()
		db := start(t, mariamem.Options{})
		defer closeDB(t, db)
		sqlCheck(t, db)
		if calls() != before {
			t.Fatal("offline startup touched network")
		}
		outcomes[t.Name()] = "PASS"
	})
	mu.Lock()
	offline = false
	mu.Unlock()
	t.Run("concurrent-first-starts", func(t *testing.T) {
		newCache()
		var wg sync.WaitGroup
		failures := make(chan error, 3)
		for i := 0; i < 3; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				db, err := mariamem.Start(ctx, mariamem.Options{})
				if err == nil {
					pool, e := sql.Open("mysql", db.DSN())
					err = e
					if e == nil {
						var n int
						err = pool.QueryRowContext(ctx, "SELECT 1").Scan(&n)
						err = errors.Join(err, pool.Close())
					}
					err = errors.Join(err, db.Close())
				}
				failures <- err
			}()
		}
		wg.Wait()
		close(failures)
		for err := range failures {
			must(t, err)
		}
		outcomes[t.Name()] = "PASS"
	})
	t.Run("corrupted-cache", func(t *testing.T) {
		cache, err := os.UserCacheDir()
		must(t, err)
		module := filepath.Join(cache, "mariamem", f.Tag, f.Target, "bundle", "mariamem.wasmu")
		must(t, os.WriteFile(module, []byte("corrupt"), 0600))
		before := calls()
		db, err := mariamem.Start(ctx, mariamem.Options{})
		if db != nil {
			db.Close()
		}
		var failure *mariamem.HostError
		if !errors.As(err, &failure) || failure.Code != "artifact_mismatch" {
			t.Fatal(err)
		}
		if calls() != before {
			t.Fatal("corrupt cache silently redownloaded")
		}
		outcomes[t.Name()] = "PASS"
	})
	for _, condition := range []string{"corrupted-download", "interrupted-download", "missing-artifact", "incompatible-version"} {
		t.Run(condition, func(t *testing.T) {
			newCache()
			mu.Lock()
			corrupt = condition == "corrupted-download"
			interrupt = condition == "interrupted-download"
			absent = condition == "missing-artifact"
			wrongVersion = condition == "incompatible-version"
			mu.Unlock()
			db, err := mariamem.Start(ctx, mariamem.Options{})
			if db != nil {
				db.Close()
			}
			if err == nil || !strings.Contains(err.Error(), f.Asset) || !strings.Contains(err.Error(), "Options.NativeDir") {
				t.Fatal(err)
			}
			cache, e := os.UserCacheDir()
			must(t, e)
			entries, e := filepath.Glob(filepath.Join(cache, "mariamem", f.Tag, "*"))
			must(t, e)
			if len(entries) != 0 {
				t.Fatalf("poisoned cache %v", entries)
			}
			mu.Lock()
			corrupt = false
			interrupt = false
			absent = false
			wrongVersion = false
			mu.Unlock()
			db = start(t, mariamem.Options{})
			sqlCheck(t, db)
			closeDB(t, db)
			outcomes[t.Name()] = "PASS"
		})
	}
	t.Run("explicit-override-offline", func(t *testing.T) {
		newCache()
		mu.Lock()
		offline = true
		mu.Unlock()
		t.Setenv("MARIAMEM_NATIVE_DIR", filepath.Join(t.TempDir(), "nonexistent-environment-override"))
		before := calls()
		db := start(t, mariamem.Options{NativeDir: os.Getenv("ZERO_NATIVE")})
		defer closeDB(t, db)
		sqlCheck(t, db)
		if calls() != before {
			t.Fatal("override used network")
		}
		outcomes[t.Name()] = "PASS"
	})
	result := "PASS"
	if t.Failed() {
		result = "FAIL"
	}
	encoded, err := json.MarshalIndent(map[string]any{"result": result, "tag": f.Tag, "target": f.Target, "archive_sha256": f.ArchiveSHA, "cases": outcomes, "requests": calls(), "go": info.GoVersion, "synthetic_release": true}, "", "  ")
	must(t, err)
	must(t, os.WriteFile(os.Getenv("ZERO_EVIDENCE"), encoded, 0600))
}
func mustJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v)
}
