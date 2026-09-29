package artifacts

import (
	"archive/tar"
	"bufio"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"runtime/debug"
	"strings"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/timing"
)

const modulePath = "github.com/masahitojp/mariamem"
const releasesURL = "https://github.com/masahitojp/mariamem/releases/download/"
const releaseAPI = "https://api.github.com/repos/masahitojp/mariamem/releases/tags/"

var releasePattern = regexp.MustCompile(`^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(alpha|beta|rc)\.([1-9][0-9]*))?$`)
var hashPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

// Automatic resolution is release-only. Replacements and pseudo-versions do
// not identify a published guest; never substitute the canonical source version.
func releaseVersion(info *debug.BuildInfo) (string, error) {
	modules := []*debug.Module{&info.Main}
	modules = append(modules, info.Deps...)
	for _, module := range modules {
		if module.Path == modulePath {
			if module.Replace == nil && releasePattern.MatchString(module.Version) {
				return module.Version, nil
			}
			return "", fmt.Errorf("mariamem build %q is untagged/development or replaced; no exact downloadable native bundle is known. Build a matching guest and set Options.NativeDir or MARIAMEM_NATIVE_DIR", module.Version)
		}
	}
	return "", errors.New("mariamem module release identity is unavailable; set Options.NativeDir or MARIAMEM_NATIVE_DIR to a matching native bundle")
}
func pythonVersion(tag string) string {
	parts := releasePattern.FindStringSubmatch(tag)
	base := strings.Join(parts[1:4], ".")
	if parts[4] == "" {
		return base
	}
	return base + map[string]string{"alpha": "a", "beta": "b", "rc": "rc"}[parts[4]] + parts[5]
}

type downloader struct {
	client                  *http.Client
	api, releases, lockHash string
	version                 func() (string, error)
	cacheRoot               func() (string, error)
}

// ResolveStartup preserves explicit/offline overrides. The cache never bypasses
// normal per-start integrity checks or the single-use verified startup identity.
func ResolveStartup(ctx context.Context, dir, lockHash string) (Bundle, error) {
	if dir == "" {
		dir = os.Getenv("MARIAMEM_NATIVE_DIR")
	}
	if dir != "" {
		return ResolveTimed(ctx, dir)
	}
	target, major, err := currentTarget(ctx)
	if err != nil {
		return Bundle{}, err
	}
	if target == "darwin-arm64" && major < 15 {
		return Bundle{}, diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("automatic native setup requires macOS 15+ arm64; got macOS %d", major))
	}
	d := downloader{api: releaseAPI, releases: releasesURL, lockHash: lockHash, cacheRoot: os.UserCacheDir,
		version: func() (string, error) {
			info, ok := debug.ReadBuildInfo()
			if !ok {
				return "", errors.New("Go build identity unavailable; set Options.NativeDir or MARIAMEM_NATIVE_DIR")
			}
			return releaseVersion(info)
		},
		client: &http.Client{Timeout: 120 * time.Second, CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) >= 10 {
				return errors.New("too many release download redirects")
			}
			if req.URL.Scheme != "https" || (req.URL.Host != "github.com" && req.URL.Host != "release-assets.githubusercontent.com" && req.URL.Host != "objects.githubusercontent.com") {
				return errors.New("release download redirected outside GitHub's canonical asset hosts")
			}
			return nil
		}},
	}
	return d.resolve(ctx, target, major)
}

type cacheReceipt struct {
	Tag             string            `json:"tag"`
	Target          string            `json:"target"`
	Asset           string            `json:"asset"`
	ArchiveSHA256   string            `json:"archive_sha256"`
	InputLockSHA256 string            `json:"inputs_lock_sha256"`
	Files           map[string]string `json:"files"`
}

func (d downloader) resolve(ctx context.Context, target string, major int) (b Bundle, err error) {
	if target != "darwin-arm64" && target != "ubuntu24.04-x86_64" {
		return b, diagnostic.Wrap("unsupported_platform", "platform", fmt.Errorf("unsupported automatic native platform %q", target))
	}
	tag, err := d.version()
	if err != nil {
		return b, diagnostic.Wrap("native_unavailable", "native_resolution", err)
	}
	if !releasePattern.MatchString(tag) {
		return b, diagnostic.Wrap("native_unavailable", "native_resolution", fmt.Errorf("no exact release identity %q; set Options.NativeDir", tag))
	}
	asset := "mariamem-native-" + target + ".tar.gz"
	root, err := d.cacheRoot()
	if err != nil {
		return b, diagnostic.Wrap("native_unavailable", "native_resolution", err)
	}
	destination := filepath.Join(root, "mariamem", tag, target)
	defer func() {
		if err != nil {
			var detail *diagnostic.Error
			code := "native_unavailable"
			if errors.As(err, &detail) {
				code = detail.Code
			}
			err = diagnostic.Wrap(code, "native_resolution", fmt.Errorf("needed %s from release %s; cache %q. Provide a complete matching bundle with Options.NativeDir or MARIAMEM_NATIVE_DIR; if cache is damaged, remove this cache entry before retrying: %w", asset, tag, destination, err))
		}
	}()
	if _, err = os.Lstat(destination); err == nil {
		return d.cached(ctx, destination, tag, target, major)
	} else if !errors.Is(err, os.ErrNotExist) {
		return b, err
	}
	if err = os.MkdirAll(filepath.Dir(destination), 0700); err != nil {
		return b, err
	}
	stage, err := os.MkdirTemp(filepath.Dir(destination), ".download-")
	if err != nil {
		return b, err
	}
	defer os.RemoveAll(stage)
	// Exact-tag metadata confirms both assets were published by this release.
	var release struct {
		Tag    string `json:"tag_name"`
		Draft  bool   `json:"draft"`
		Assets []struct {
			Name   string `json:"name"`
			URL    string `json:"browser_download_url"`
			Digest string `json:"digest"`
		} `json:"assets"`
	}
	raw, err := d.get(ctx, d.api+tag, 2<<20)
	if err != nil {
		return b, err
	}
	if err = json.Unmarshal(raw, &release); err != nil {
		return b, err
	}
	if release.Tag != tag || release.Draft {
		return b, errors.New("release tag differs or release is not published")
	}
	urls := map[string]string{}
	digests := map[string]string{}
	for _, a := range release.Assets {
		if a.Name == asset || a.Name == "SHA256SUMS" {
			if urls[a.Name] != "" || a.URL != d.releases+tag+"/"+a.Name {
				return b, errors.New("release has duplicate or noncanonical asset URL")
			}
			urls[a.Name] = a.URL
			digests[a.Name] = a.Digest
		}
	}
	if urls[asset] == "" || urls["SHA256SUMS"] == "" {
		return b, errors.New("exact release native asset or SHA256SUMS is unavailable")
	}
	sums, err := d.get(ctx, urls["SHA256SUMS"], 64<<10)
	if err != nil {
		return b, err
	}
	if digests["SHA256SUMS"] != "" && digests["SHA256SUMS"] != "sha256:"+digestBytes(sums) {
		return b, mismatch("published SHA256SUMS digest differs")
	}
	expected, err := checksum(sums, asset)
	if err != nil {
		return b, mismatch(err.Error())
	}
	if digests[asset] != "" && digests[asset] != "sha256:"+expected {
		return b, mismatch("release asset digest and SHA256SUMS disagree")
	}
	archive, err := os.CreateTemp(stage, "archive-")
	if err != nil {
		return b, err
	}
	defer archive.Close()
	hash := sha256.New()
	if err = d.getTo(ctx, urls[asset], 128<<20, io.MultiWriter(archive, hash)); err != nil {
		return b, err
	}
	if hex.EncodeToString(hash.Sum(nil)) != expected {
		return b, mismatch("downloaded archive SHA256 mismatch")
	}
	if _, err = archive.Seek(0, io.SeekStart); err != nil {
		return b, err
	}
	files, err := extractNative(archive, stage, "mariamem-native-"+target)
	if err != nil {
		return b, mismatch(err.Error())
	}
	if err = archive.Close(); err != nil {
		return b, err
	}
	if err = os.Remove(archive.Name()); err != nil {
		return b, err
	}
	receipt := cacheReceipt{Tag: tag, Target: target, Asset: asset, ArchiveSHA256: expected, InputLockSHA256: d.lockHash, Files: files}
	encoded, err := json.Marshal(receipt)
	if err != nil {
		return b, err
	}
	if err = os.WriteFile(filepath.Join(stage, "receipt.json"), encoded, 0600); err != nil {
		return b, err
	}
	if _, err = d.cached(ctx, stage, tag, target, major); err != nil {
		return b, err
	}
	if err = ctx.Err(); err != nil {
		return b, err
	}
	if err = os.Rename(stage, destination); err != nil {
		// Another process may have installed the same verified release first.
		if _, statErr := os.Lstat(destination); statErr != nil {
			return b, err
		}
	}
	return d.cached(ctx, destination, tag, target, major)
}

func mismatch(message string) error {
	return diagnostic.Wrap("artifact_mismatch", "native_resolution", errors.New(message))
}
func digestBytes(data []byte) string { sum := sha256.Sum256(data); return hex.EncodeToString(sum[:]) }
func checksum(data []byte, name string) (string, error) {
	scanner := bufio.NewScanner(strings.NewReader(string(data)))
	found := ""
	for scanner.Scan() {
		fields := strings.Fields(scanner.Text())
		if len(fields) == 2 && fields[1] == name {
			if found != "" || !hashPattern.MatchString(fields[0]) {
				return "", errors.New("duplicate or invalid native checksum")
			}
			found = fields[0]
		}
	}
	if err := scanner.Err(); err != nil {
		return "", err
	}
	if found == "" {
		return "", errors.New("native asset missing from SHA256SUMS")
	}
	return found, nil
}
func (d downloader) get(ctx context.Context, url string, limit int64) ([]byte, error) {
	var buf bytes.Buffer
	err := d.getTo(ctx, url, limit, &buf)
	return buf.Bytes(), err
}
func (d downloader) getTo(ctx context.Context, url string, limit int64, writer io.Writer) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "mariamem-native-setup")
	req.Header.Set("Accept", "application/octet-stream")
	if strings.HasPrefix(url, d.api) {
		req.Header.Set("Accept", "application/vnd.github+json")
	}
	response, err := d.client.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("download %s: HTTP %d", url, response.StatusCode)
	}
	count, err := io.Copy(writer, io.LimitReader(response.Body, limit+1))
	if err != nil {
		return err
	}
	if count > limit {
		return errors.New("release response exceeds size limit")
	}
	return nil
}

func extractNative(data io.Reader, stage, prefix string) (map[string]string, error) {
	reader, err := gzip.NewReader(data)
	if err != nil {
		return nil, err
	}
	defer reader.Close()
	bounded := &io.LimitedReader{R: reader, N: (512 << 20) + (2 << 20)}
	tarReader := tar.NewReader(bounded)
	files := map[string]string{}
	var total int64
	for {
		header, err := tarReader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		name := strings.TrimPrefix(header.Name, prefix+"/")
		if name == header.Name || name == "." || path.Clean(name) != name || strings.HasPrefix(name, "../") || strings.HasPrefix(name, "/") || strings.Contains(name, "\\") {
			return nil, errors.New("unsafe native archive path")
		}
		allowed := name == "manifest.json" || name == "CANDIDATE.json" || name == "wasmer-headless" || name == "mariamem.wasmu" || name == "mariamem.wasmu.json" || name == "LICENSE" || name == "NOTICE" || name == "THIRD_PARTY_LICENSES" || strings.HasPrefix(name, "licenses/")
		total += header.Size
		if !allowed || header.Typeflag != tar.TypeReg || header.Size < 0 || total > 512<<20 || len(files) >= 128 || files[name] != "" {
			return nil, errors.New("unexpected, oversized or duplicate native archive entry")
		}
		mode := os.FileMode(0600)
		if name == "wasmer-headless" {
			mode = 0700
		}
		filename := filepath.Join(stage, "bundle", filepath.FromSlash(name))
		if err = os.MkdirAll(filepath.Dir(filename), 0700); err != nil {
			return nil, err
		}
		file, err := os.OpenFile(filename, os.O_CREATE|os.O_EXCL|os.O_WRONLY, mode)
		if err != nil {
			return nil, err
		}
		hash := sha256.New()
		_, copyErr := io.Copy(io.MultiWriter(file, hash), tarReader)
		closeErr := file.Close()
		if err = errors.Join(copyErr, closeErr); err != nil {
			return nil, err
		}
		files[name] = hex.EncodeToString(hash.Sum(nil))
	}
	// Read through the gzip trailer as well, so truncation/CRC errors cannot be hidden.
	if _, err = io.Copy(io.Discard, bounded); err != nil {
		return nil, err
	}
	if bounded.N == 0 {
		return nil, errors.New("native archive expanded beyond limit")
	}
	for _, name := range []string{"manifest.json", "CANDIDATE.json", "wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json", "LICENSE", "NOTICE", "THIRD_PARTY_LICENSES"} {
		if files[name] == "" {
			return nil, fmt.Errorf("native archive missing %s", name)
		}
	}
	return files, nil
}

func (d downloader) cached(ctx context.Context, entry, tag, target string, major int) (Bundle, error) {
	info, err := os.Lstat(entry)
	if err != nil {
		return Bundle{}, err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return Bundle{}, mismatch("cache entry is not a directory")
	}
	raw, err := os.ReadFile(filepath.Join(entry, "receipt.json"))
	if err != nil {
		return Bundle{}, mismatch("cache receipt missing")
	}
	var receipt cacheReceipt
	if err = json.Unmarshal(raw, &receipt); err != nil {
		return Bundle{}, mismatch("invalid cache receipt")
	}
	if receipt.Tag != tag || receipt.Target != target || receipt.Asset != "mariamem-native-"+target+".tar.gz" || !hashPattern.MatchString(receipt.ArchiveSHA256) || receipt.InputLockSHA256 != d.lockHash {
		return Bundle{}, mismatch("cache release/input identity differs")
	}
	dir := filepath.Join(entry, "bundle")
	if info, err := os.Lstat(dir); err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return Bundle{}, mismatch("cache bundle is not a directory")
	}
	if len(receipt.Files) > 128 {
		return Bundle{}, mismatch("oversized cache inventory")
	}
	for name, expected := range receipt.Files {
		if path.Clean(name) != name || strings.HasPrefix(name, "../") || path.IsAbs(name) || strings.Contains(name, "\\") || !hashPattern.MatchString(expected) {
			return Bundle{}, mismatch("unsafe cache inventory")
		}
		file := filepath.Join(dir, filepath.FromSlash(name))
		info, err := os.Lstat(file)
		if err != nil || !info.Mode().IsRegular() {
			return Bundle{}, mismatch("cached file missing/nonregular: " + name)
		}
		if name == "wasmer-headless" || name == "mariamem.wasmu" || name == "mariamem.wasmu.json" {
			continue
		} // normal Resolve hashes these below
		opened, err := os.Open(file)
		if err != nil {
			return Bundle{}, err
		}
		hash := sha256.New()
		_, copyErr := io.Copy(hash, opened)
		if err = errors.Join(copyErr, opened.Close()); err != nil {
			return Bundle{}, err
		}
		if hex.EncodeToString(hash.Sum(nil)) != expected {
			return Bundle{}, mismatch("cached file checksum mismatch: " + name)
		}
	}
	for _, name := range []string{"manifest.json", "CANDIDATE.json", "LICENSE", "NOTICE", "THIRD_PARTY_LICENSES"} {
		if receipt.Files[name] == "" {
			return Bundle{}, mismatch("cache inventory incomplete")
		}
	}
	var manifest struct {
		Package string            `json:"package_version"`
		Hashes  map[string]string `json:"sha256"`
	}
	raw, err = os.ReadFile(filepath.Join(dir, "manifest.json"))
	if err != nil {
		return Bundle{}, err
	}
	if err = json.Unmarshal(raw, &manifest); err != nil {
		return Bundle{}, err
	}
	if manifest.Package != pythonVersion(tag) {
		return Bundle{}, mismatch("native package version differs from Go release")
	}
	for _, name := range []string{"wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json"} {
		if receipt.Files[name] == "" || receipt.Files[name] != manifest.Hashes[name] {
			return Bundle{}, mismatch("native manifest and cache inventory differ: " + name)
		}
	}
	var candidate struct {
		Lock string `json:"inputs_lock_sha256"`
	}
	raw, err = os.ReadFile(filepath.Join(dir, "CANDIDATE.json"))
	if err != nil {
		return Bundle{}, err
	}
	if err = json.Unmarshal(raw, &candidate); err != nil {
		return Bundle{}, err
	}
	if candidate.Lock != d.lockHash {
		return Bundle{}, mismatch("native candidate provenance differs from this Go module's pinned inputs")
	}
	ctx, finish := timing.Begin(ctx, "native_verification")
	defer finish()
	return resolveTimed(ctx, dir, target, major)
}
