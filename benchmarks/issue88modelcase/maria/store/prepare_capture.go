// Issue140: one polling watcher; no timer/goroutine is created per PREPARE.
package store

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"path/filepath"
	"runtime/pprof"
	"sync"
	"sync/atomic"
	"time"
)

type PrepareCapture struct {
	ReadBefore      []base.ReadSnapshot `json:"read_before"`
	ReadAfter       []base.ReadSnapshot `json:"read_after"`
	DBID            string              `json:"db_id"`
	Lane            string              `json:"lane"`
	Phase           string              `json:"phase"`
	Ordinal         int                 `json:"prepare_ordinal"`
	CallEnterUS     int64               `json:"call_enter_us"`
	CallReturnUS    int64               `json:"call_return_us"`
	SnapshotBeginUS int64               `json:"snapshot_begin_us"`
	SnapshotEndUS   int64               `json:"snapshot_end_us"`
	Truncated       bool                `json:"truncated"`
	Bytes           int                 `json:"bytes"`
	ProfileFile     string              `json:"profile_file"`
	Error           string              `json:"error,omitempty"`
	returned        atomic.Int64
	clock           func() int64
	data            []byte
}

var prepareCaptureUsed atomic.Bool
var prepareCaptures []*PrepareCapture // written by watcher; read after watcher joined
var prepareActive sync.Map            // db_id -> *atomic.Pointer[PrepareCapture]
var prepareWatchOnce sync.Once
var prepareWatchStarted atomic.Bool
var prepareWatchStop = make(chan struct{})
var prepareWatchDone = make(chan struct{})
var prepareWatchStopOnce sync.Once
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
func pollPrepareCalls() {
	defer close(prepareWatchDone)
	ticker := time.NewTicker(20 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-prepareWatchStop:
			return
		case <-ticker.C:
			prepareActive.Range(func(_, value any) bool {
				c := value.(*atomic.Pointer[PrepareCapture]).Load()
				if c == nil || c.returned.Load() != 0 || c.clock()-c.CallEnterUS < 100000 {
					return true
				}
				if !prepareCaptureUsed.CompareAndSwap(false, true) {
					return false
				}
				c.SnapshotBeginUS = c.clock()
				c.ReadBefore = base.SnapshotReadObservation(c.DBID)
				var b boundedProfile
				err := pprof.Lookup("goroutine").WriteTo(&b, 1)
				c.ReadAfter = base.SnapshotReadObservation(c.DBID)
				c.SnapshotEndUS = c.clock()
				c.data = append([]byte(nil), b.Bytes()...)
				c.Bytes = len(c.data)
				c.Truncated = b.truncated
				if err != nil {
					c.Error = err.Error()
				}
				prepareCaptures = append(prepareCaptures, c)
				return false
			})
			if prepareCaptureUsed.Load() {
				return
			}
		}
	}
}
func startPrepareCapture(o *sampleObserver, phase string, ordinal int) func() {
	if !prepareCaptureEnabled || o == nil || prepareCaptureUsed.Load() || (phase != "positive_control" && prepareControlOnly) {
		return nil
	}
	prepareWatchOnce.Do(func() { prepareWatchStarted.Store(true); go pollPrepareCalls() })
	value, _ := prepareActive.LoadOrStore(o.dbID, &atomic.Pointer[PrepareCapture]{})
	active := value.(*atomic.Pointer[PrepareCapture])
	c := &PrepareCapture{DBID: o.dbID, Lane: o.lane, Phase: phase, Ordinal: ordinal, CallEnterUS: o.clock(), clock: o.clock}
	active.Store(c)
	return func() { c.returned.Store(o.clock()); active.CompareAndSwap(c, nil) }
}
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

// Called after all cases return. Join watcher and serialize outside suite timing.
func WritePrepareCaptures(dir string) error {
	if prepareWatchStarted.Load() {
		prepareWatchStopOnce.Do(func() { close(prepareWatchStop) })
		<-prepareWatchDone
	}
	if dir == "" {
		return nil
	}
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	for i, c := range prepareCaptures {
		c.CallReturnUS = c.returned.Load()
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
