package generatedgo

import (
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"strings"
	"sync/atomic"
	"syscall"
)

var bpFaultPath atomic.Value
var bpFaultArmed atomic.Bool
var bpFaultHits atomic.Int64

func SetBufferFault(path string) {
	bpFaultPath.Store(path)
	bpFaultHits.Store(0)
	bpFaultArmed.Store(path != "")
}
func BufferFaultHits() int64 { return bpFaultHits.Load() }

type bpFaultFS struct{ entropyFS }
type bpFaultFile struct {
	base.File
	path string
}

func newBPFaultFS(f *base.MemFS) base.FS { return bpFaultFS{entropyFS{f}} }
func (f bpFaultFS) OpenFile(name string, flags int, mode os.FileMode) (base.File, error) {
	v, e := f.entropyFS.OpenFile(name, flags, mode)
	if e != nil {
		return nil, e
	}
	if strings.HasSuffix(name, "/faultprobe.ibd") || strings.HasSuffix(name, "/ibdata1") {
		return &bpFaultFile{v, name}, nil
	}
	return v, nil
}
func (f *bpFaultFile) fault() bool {
	p, _ := bpFaultPath.Load().(string)
	if p != "" && strings.HasSuffix(f.path, p) && bpFaultArmed.CompareAndSwap(true, false) {
		bpFaultHits.Add(1)
		return true
	}
	return false
}
func (f *bpFaultFile) ReadAt(p []byte, off int64) (int, error) {
	if f.fault() {
		return 0, syscall.EIO
	}
	return f.File.ReadAt(p, off)
}
func (f *bpFaultFile) Read(p []byte) (int, error) {
	if f.fault() {
		return 0, syscall.EIO
	}
	return f.File.Read(p)
}
