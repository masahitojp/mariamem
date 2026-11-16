package guest

import (
	"io"
	"os"
	"sync"
	"sync/atomic"
)

// Experiment only: replace only guest->host stdout. No product selection API.
func experimentResponsePipe() (io.ReadCloser, io.WriteCloser, error) {
	if os.Getenv("RESPONSE_PIPE") == "go" {
		r, w := io.Pipe()
		return r, w, nil
	}
	return os.Pipe()
}

var experimentEnabled atomic.Bool
var experimentMu sync.Mutex
var experimentStats map[string]map[int]int64

func ExperimentBegin() {
	experimentMu.Lock()
	experimentStats = make(map[string]map[int]int64)
	experimentMu.Unlock()
	experimentEnabled.Store(true)
}
func ExperimentEnd() map[string]map[int]int64 {
	experimentEnabled.Store(false)
	experimentMu.Lock()
	defer experimentMu.Unlock()
	return experimentStats
}
func experimentCount(k string, n int) {
	if !experimentEnabled.Load() {
		return
	}
	experimentMu.Lock()
	defer experimentMu.Unlock()
	if experimentStats[k] == nil {
		experimentStats[k] = map[int]int64{}
	}
	experimentStats[k][n]++
}

type observedReader struct {
	k string
	r io.Reader
}

func (x observedReader) Read(b []byte) (int, error) {
	n, e := x.r.Read(b)
	experimentCount(x.k+"_requested", len(b))
	experimentCount(x.k+"_actual", n)
	return n, e
}

type observedWriter struct {
	k string
	w io.Writer
}

func (x observedWriter) Write(b []byte) (int, error) {
	n, e := x.w.Write(b)
	experimentCount(x.k+"_requested", len(b))
	experimentCount(x.k+"_actual", n)
	return n, e
}
func experimentReader(k string, r io.Reader) io.Reader {
	if os.Getenv("TRANSPORT_DIAG") == "1" {
		return observedReader{k, r}
	}
	return r
}
func experimentWriter(k string, w io.Writer) io.Writer {
	if os.Getenv("TRANSPORT_DIAG") == "1" {
		return observedWriter{k, w}
	}
	return w
}

type observedReadCloser struct {
	io.Reader
	io.Closer
}
type observedWriteCloser struct {
	io.Writer
	io.Closer
}

func experimentReadCloser(k string, r io.ReadCloser) io.ReadCloser {
	return observedReadCloser{experimentReader(k, r), r}
}
func experimentWriteCloser(k string, w io.WriteCloser) io.WriteCloser {
	return observedWriteCloser{experimentWriter(k, w), w}
}
