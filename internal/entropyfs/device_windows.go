package entropyfs

import (
	"crypto/rand"
	"io"
	"os"
	"path"
	"sync"
	"syscall"
	"time"
)

type File struct {
	mu     sync.Mutex
	name   string
	closed bool
}
type info struct{ name string }

func (i info) Name() string     { return path.Base(i.name) }
func (info) Size() int64        { return 0 }
func (info) Mode() os.FileMode  { return os.ModeDevice | os.ModeCharDevice | 0444 }
func (info) ModTime() time.Time { return time.Unix(0, 0) }
func (info) IsDir() bool        { return false }
func (info) Sys() any           { return nil }
func Open(name string) (*File, error) {
	if !allowed(name) {
		return nil, os.ErrNotExist
	}
	return &File{name: name}, nil
}
func Stat(name string) (os.FileInfo, error) {
	if !allowed(name) {
		return nil, os.ErrNotExist
	}
	return info{name}, nil
}
func (f *File) Name() string { return f.name }
func (f *File) Read(p []byte) (int, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.closed {
		return 0, os.ErrClosed
	}
	return io.ReadFull(rand.Reader, p)
}
func (f *File) Stat() (os.FileInfo, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.closed {
		return nil, os.ErrClosed
	}
	return info{f.name}, nil
}
func (f *File) Close() error                     { f.mu.Lock(); defer f.mu.Unlock(); f.closed = true; return nil }
func (*File) ReadAt([]byte, int64) (int, error)  { return 0, syscall.ESPIPE }
func (*File) Write([]byte) (int, error)          { return 0, os.ErrPermission }
func (*File) WriteAt([]byte, int64) (int, error) { return 0, os.ErrPermission }
func (*File) Seek(int64, int) (int64, error)     { return 0, syscall.ESPIPE }
func (*File) ReadDir(int) ([]os.DirEntry, error) { return nil, syscall.ENOTDIR }
func (*File) Sync() error                        { return syscall.EINVAL }
func (*File) Truncate(int64) error               { return os.ErrPermission }
