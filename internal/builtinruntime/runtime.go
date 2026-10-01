// Package builtinruntime owns the checksum-bound, built-in generated guest image.
package builtinruntime

import (
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// Prepare materializes a dedicated guest in this DB's private temporary directory.
// It never executes the consumer, resolves Wasmer, downloads or uses a user cache.
func Prepare(ctx context.Context, dir string) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	data, expected, err := image()
	if err != nil {
		return "", err
	}
	zipped, err := gzip.NewReader(base64.NewDecoder(base64.StdEncoding, strings.NewReader(data)))
	if err != nil {
		return "", err
	}
	defer zipped.Close()
	path := filepath.Join(dir, "mariamem-guest")
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return "", err
	}
	h := sha256.New()
	_, err = io.Copy(io.MultiWriter(f, h), contextReader{ctx, zipped})
	closeErr := f.Close()
	if err == nil {
		err = closeErr
	}
	if err != nil {
		os.Remove(path)
		return "", err
	}
	if hex.EncodeToString(h.Sum(nil)) != expected {
		os.Remove(path)
		return "", fmt.Errorf("built-in generated runtime checksum mismatch")
	}
	if err = os.Chmod(path, 0700); err != nil {
		os.Remove(path)
		return "", err
	}
	return path, nil
}

type contextReader struct {
	ctx context.Context
	r   io.Reader
}

func (r contextReader) Read(p []byte) (int, error) {
	if err := r.ctx.Err(); err != nil {
		return 0, err
	}
	return r.r.Read(p)
}
