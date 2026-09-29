package artifacts

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime/debug"
	"strings"
	"sync"
	"testing"
)

type transportFunc func(*http.Request) (*http.Response, error)

func (f transportFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func TestReleaseBuildIdentity(t *testing.T) {
	for _, tag := range []string{"v0.2.0", "v0.3.0-alpha.1", "v0.3.0-beta.2", "v0.3.0-rc.1"} {
		got, err := releaseVersion(&debug.BuildInfo{Deps: []*debug.Module{{Path: modulePath, Version: tag}}})
		if err != nil || got != tag {
			t.Fatal(got, err)
		}
	}
	for _, version := range []string{"(devel)", "", "v0.2.1-0.20260929104630-d036296708ae", "v0.3.0-alpha.0", "v00.2.0"} {
		if _, err := releaseVersion(&debug.BuildInfo{Main: debug.Module{Path: modulePath, Version: version}}); err == nil {
			t.Fatal(version)
		}
	}
	if _, err := releaseVersion(&debug.BuildInfo{Deps: []*debug.Module{{Path: modulePath, Version: "v0.2.0", Replace: &debug.Module{Path: "local"}}}}); err == nil {
		t.Fatal("replacement trusted")
	}
	if pythonVersion("v0.3.0-rc.1") != "0.3.0rc1" || pythonVersion("v0.2.0") != "0.2.0" {
		t.Fatal("Python version")
	}
}

func downloadFixture(t *testing.T, alter func(map[string][]byte)) (downloader, *int, *sync.Mutex) {
	return platformDownloadFixture(t, "darwin-arm64", alter)
}
func platformDownloadFixture(t *testing.T, target string, alter func(map[string][]byte)) (downloader, *int, *sync.Mutex) {
	t.Helper()
	dir := fixture(t)
	files := map[string][]byte{}
	for _, name := range []string{"wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json", "manifest.json"} {
		data, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil {
			t.Fatal(err)
		}
		files[name] = data
	}
	var m map[string]any
	json.Unmarshal(files["manifest.json"], &m)
	m["package_version"] = "0.3.0a1"
	if target == "ubuntu24.04-x86_64" {
		m["platform"] = target
		m["distribution"] = "ubuntu"
		m["version_id"] = "24.04"
		m["architecture"] = "x86_64"
		delete(m, "minimum_macos")
	}
	files["manifest.json"], _ = json.Marshal(m)
	lock := strings.Repeat("b", 64)
	files["CANDIDATE.json"] = []byte(`{"inputs_lock_sha256":"` + lock + `"}`)
	for _, name := range []string{"LICENSE", "NOTICE", "THIRD_PARTY_LICENSES", "licenses/test.txt"} {
		files[name] = []byte("notice")
	}
	if alter != nil {
		alter(files)
	}
	var buffer bytes.Buffer
	gz := gzip.NewWriter(&buffer)
	tw := tar.NewWriter(gz)
	for name, data := range files {
		if err := tw.WriteHeader(&tar.Header{Name: "mariamem-native-" + target + "/" + name, Mode: 0600, Size: int64(len(data)), Typeflag: tar.TypeReg}); err != nil {
			t.Fatal(err)
		}
		tw.Write(data)
	}
	tw.Close()
	gz.Close()
	archive := buffer.Bytes()
	tag := "v0.3.0-alpha.1"
	asset := "mariamem-native-" + target + ".tar.gz"
	api := "https://fixture.invalid/api/"
	base := "https://fixture.invalid/releases/"
	sums := []byte(fmt.Sprintf("%s  %s\n", digestBytes(archive), asset))
	metadata, _ := json.Marshal(map[string]any{"tag_name": tag, "draft": false, "assets": []map[string]string{{"name": asset, "browser_download_url": base + tag + "/" + asset, "digest": "sha256:" + digestBytes(archive)}, {"name": "SHA256SUMS", "browser_download_url": base + tag + "/SHA256SUMS", "digest": "sha256:" + digestBytes(sums)}}})
	count := new(int)
	mu := new(sync.Mutex)
	d := downloader{api: api, releases: base, lockHash: lock, version: func() (string, error) { return tag, nil }, cacheRoot: func() (string, error) { return dir, nil }}
	d.client = &http.Client{Transport: transportFunc(func(req *http.Request) (*http.Response, error) {
		mu.Lock()
		*count++
		mu.Unlock()
		var data []byte
		switch req.URL.String() {
		case api + tag:
			data = metadata
		case base + tag + "/SHA256SUMS":
			data = sums
		case base + tag + "/" + asset:
			data = archive
		default:
			return nil, fmt.Errorf("unexpected URL %s", req.URL)
		}
		return &http.Response{StatusCode: 200, Body: io.NopCloser(bytes.NewReader(data)), Header: make(http.Header)}, nil
	})}
	return d, count, mu
}
func TestDownloadCacheOffline(t *testing.T) {
	d, count, _ := downloadFixture(t, nil)
	b, err := d.resolve(context.Background(), "darwin-arm64", 15)
	if err != nil {
		t.Fatal(err)
	}
	if *count != 3 {
		t.Fatal(*count)
	}
	d.client = &http.Client{Transport: transportFunc(func(*http.Request) (*http.Response, error) {
		t.Error("cache accessed network")
		return nil, errors.New("offline")
	})}
	second, err := d.resolve(context.Background(), "darwin-arm64", 15)
	if err != nil || b.Dir != second.Dir {
		t.Fatal(second, err)
	}
	if err := os.WriteFile(filepath.Join(b.Dir, "mariamem.wasmu"), []byte("corrupt"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = d.resolve(context.Background(), "darwin-arm64", 15); err == nil || !strings.Contains(err.Error(), "mismatch") {
		t.Fatal(err)
	}
}
func TestDownloadMismatchAndAtomicFailure(t *testing.T) {
	for _, kind := range []string{"version", "provenance", "missing", "manifest", "unsafe", "download", "cancel", "unavailable"} {
		t.Run(kind, func(t *testing.T) {
			d, _, _ := downloadFixture(t, func(f map[string][]byte) {
				switch kind {
				case "version":
					f["manifest.json"] = bytes.ReplaceAll(f["manifest.json"], []byte("0.3.0a1"), []byte("0.2.0"))
				case "provenance":
					f["CANDIDATE.json"] = []byte(`{"inputs_lock_sha256":"bad"}`)
				case "missing":
					delete(f, "NOTICE")
				case "manifest":
					f["mariamem.wasmu"] = []byte("changed")
				case "unsafe":
					f["../escape"] = []byte("bad")
				}
			})
			ctx := context.Background()
			if kind == "cancel" {
				cancelCtx, cancel := context.WithCancel(ctx)
				cancel()
				ctx = cancelCtx
			}
			if kind == "download" || kind == "unavailable" {
				original := d.client.Transport
				d.client.Transport = transportFunc(func(r *http.Request) (*http.Response, error) {
					response, err := original.RoundTrip(r)
					if err == nil && strings.HasSuffix(r.URL.Path, "tar.gz") {
						response.Body = io.NopCloser(strings.NewReader("truncated"))
					}
					if kind == "unavailable" {
						response.StatusCode = 404
					}
					return response, err
				})
			}
			if _, err := d.resolve(ctx, "darwin-arm64", 15); err == nil {
				t.Fatal("failure accepted")
			}
			root, _ := d.cacheRoot()
			dest := filepath.Join(root, "mariamem", "v0.3.0-alpha.1", "darwin-arm64")
			if _, err := os.Stat(dest); !errors.Is(err, os.ErrNotExist) {
				t.Fatalf("poisoned cache: %v", err)
			}
			staging, _ := filepath.Glob(filepath.Join(filepath.Dir(dest), ".download-*"))
			if len(staging) != 0 {
				t.Fatal(staging)
			}
		})
	}
}
func TestConcurrentInstall(t *testing.T) {
	d, _, _ := downloadFixture(t, nil)
	var wg sync.WaitGroup
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, err := d.resolve(context.Background(), "darwin-arm64", 15); err != nil {
				t.Error(err)
			}
		}()
	}
	wg.Wait()
}
func TestUnsupportedResolution(t *testing.T) {
	d, _, _ := downloadFixture(t, nil)
	if _, err := d.resolve(context.Background(), "linux-arm64", 0); err == nil || !strings.Contains(err.Error(), "unsupported") {
		t.Fatal(err)
	}
}

func TestUbuntuDownload(t *testing.T) {
	d, _, _ := platformDownloadFixture(t, "ubuntu24.04-x86_64", nil)
	if _, err := d.resolve(context.Background(), "ubuntu24.04-x86_64", 0); err != nil {
		t.Fatal(err)
	}
}
func TestCacheMetadataCorruption(t *testing.T) {
	for _, name := range []string{"receipt.json", "manifest.json", "CANDIDATE.json", "NOTICE", "mariamem.wasmu.json", "wasmer-headless"} {
		t.Run(name, func(t *testing.T) {
			d, count, _ := downloadFixture(t, nil)
			b, err := d.resolve(context.Background(), "darwin-arm64", 15)
			if err != nil {
				t.Fatal(err)
			}
			path := filepath.Join(b.Dir, name)
			if name == "receipt.json" {
				path = filepath.Join(filepath.Dir(b.Dir), name)
			}
			if err := os.WriteFile(path, []byte("damaged"), 0600); err != nil {
				t.Fatal(err)
			}
			if _, err := d.resolve(context.Background(), "darwin-arm64", 15); err == nil {
				t.Fatal("corrupt metadata accepted")
			}
			if *count != 3 {
				t.Fatal("silently redownloaded")
			}
		})
	}
}
func TestRetryAfterFailedDownload(t *testing.T) {
	d, _, _ := downloadFixture(t, nil)
	client := d.client
	d.client = &http.Client{Transport: transportFunc(func(*http.Request) (*http.Response, error) { return nil, errors.New("offline") })}
	if _, err := d.resolve(context.Background(), "darwin-arm64", 15); err == nil || !strings.Contains(err.Error(), "Options.NativeDir") {
		t.Fatal(err)
	}
	d.client = client
	if _, err := d.resolve(context.Background(), "darwin-arm64", 15); err != nil {
		t.Fatal(err)
	}
}

func TestInterruptedDownload(t *testing.T) {
	d, _, _ := downloadFixture(t, nil)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	original := d.client.Transport
	d.client.Transport = transportFunc(func(r *http.Request) (*http.Response, error) {
		if strings.HasSuffix(r.URL.Path, "tar.gz") {
			cancel()
			return nil, context.Canceled
		}
		return original.RoundTrip(r)
	})
	if _, err := d.resolve(ctx, "darwin-arm64", 15); !errors.Is(err, context.Canceled) {
		t.Fatal(err)
	}
	root, _ := d.cacheRoot()
	entries, _ := filepath.Glob(filepath.Join(root, "mariamem", "v0.3.0-alpha.1", "*"))
	if len(entries) != 0 {
		t.Fatal(entries)
	}
}
