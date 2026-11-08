// Bounded caller-scope stack capture, experiment only. No guest/runtime hooks.
package store

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime/pprof"
	"sync"
	"sync/atomic"
	"time"
)

type PrepareCapture struct {
	DBID            string `json:"db_id"`
	Lane            string `json:"lane"`
	Phase           string `json:"phase"`
	Ordinal         int    `json:"prepare_ordinal"`
	CallEnterUS     int64  `json:"call_enter_us"`
	CallReturnUS    int64  `json:"call_return_us"`
	SnapshotBeginUS int64  `json:"snapshot_begin_us"`
	SnapshotEndUS   int64  `json:"snapshot_end_us"`
	Truncated       bool   `json:"truncated"`
	Bytes           int    `json:"bytes"`
	ProfileFile     string `json:"profile_file"`
	Error           string `json:"error,omitempty"`
	mu              sync.Mutex
	data            []byte
}

var prepareCaptureUsed atomic.Bool
var prepareCaptureWG sync.WaitGroup
var prepareCaptureMu sync.Mutex
var prepareCaptures []*PrepareCapture
var prepareCaptureEnabled = os.Getenv("ISSUE68_CAPTURE") == "1"
var prepareControlOnly = os.Getenv("ISSUE68_CONTROL") == "1"

type boundedProfile struct {
	bytes.Buffer
	truncated bool
}

func (b *boundedProfile) Write(p []byte) (int, error) {
	n := len(p)
	remaining := (2 << 20) - b.Len()
	if len(p) > remaining {
		b.truncated = true
		p = p[:remaining]
	}
	_, _ = b.Buffer.Write(p)
	return n, nil
}
func startPrepareCapture(o *sampleObserver, phase string, ordinal int) func() {
	if !prepareCaptureEnabled || o == nil || prepareCaptureUsed.Load() || (phase != "positive_control" && prepareControlOnly) {
		return nil
	}
	c := &PrepareCapture{DBID: o.dbID, Lane: o.lane, Phase: phase, Ordinal: ordinal, CallEnterUS: o.clock()}
	prepareCaptureWG.Add(1)
	timer := time.AfterFunc(100*time.Millisecond, func() {
		defer prepareCaptureWG.Done()
		c.mu.Lock()
		if c.CallReturnUS != 0 || !prepareCaptureUsed.CompareAndSwap(false, true) {
			c.mu.Unlock()
			return
		}
		c.SnapshotBeginUS = o.clock()
		c.mu.Unlock()
		var b boundedProfile
		err := pprof.Lookup("goroutine").WriteTo(&b, 1)
		c.mu.Lock()
		c.SnapshotEndUS = o.clock()
		c.data = append([]byte(nil), b.Bytes()...)
		c.Bytes = len(c.data)
		c.Truncated = b.truncated
		if err != nil {
			c.Error = err.Error()
		}
		c.mu.Unlock()
		prepareCaptureMu.Lock()
		prepareCaptures = append(prepareCaptures, c)
		prepareCaptureMu.Unlock()
	})
	return func() {
		end := o.clock()
		c.mu.Lock()
		c.CallReturnUS = end
		c.mu.Unlock()
		if timer.Stop() {
			prepareCaptureWG.Done()
		}
	}
}

// Positive control: actual SQL-side sleep, same caller window and DB-owner label.
func CapturePositiveControl(ctx context.Context, f func() error) error {
	o, ok := ctx.Value(sampleObserverKey{}).(sampleObserver)
	if !ok {
		return fmt.Errorf("control observer absent")
	}
	stop := startPrepareCapture(&o, "positive_control", 0)
	e := f()
	if stop != nil {
		stop()
	}
	return e
}

// Call only after all test operations returned. Serialization is outside suite time.
func WritePrepareCaptures(dir string) error {
	prepareCaptureWG.Wait()
	if dir == "" {
		return nil
	}
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	for i, c := range prepareCaptures {
		c.ProfileFile = fmt.Sprintf("profile-%d.txt", i)
		if err := os.WriteFile(filepath.Join(dir, c.ProfileFile), c.data, 0600); err != nil {
			return err
		}
		b, e := json.MarshalIndent(c, "", "  ")
		if e != nil {
			return e
		}
		if e = os.WriteFile(filepath.Join(dir, fmt.Sprintf("capture-%d.json", i)), append(b, '\n'), 0600); e != nil {
			return e
		}
	}
	return nil
}
