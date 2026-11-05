package probe

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime/pprof"
	"strings"
	"sync/atomic"
	"time"
)

var updateCaptures atomic.Uint32

// This observer does not change the statement or transaction mode.
type updateMeta struct {
	ExecEnterMS     float64 `json:"exec_enter_ms"`
	InsideExec      bool    `json:"snapshot_inside_actual_exec"`
	Child           int     `json:"child"`
	Artificial      bool    `json:"artificial"`
	ThresholdMS     int     `json:"threshold_ms"`
	SnapshotBeginMS float64 `json:"snapshot_begin_ms"`
	SnapshotEndMS   float64 `json:"snapshot_end_ms"`
	ExecReturnMS    float64 `json:"exec_return_ms"`
	Bytes           int     `json:"bytes"`
	Truncated       bool    `json:"truncated"`
	LabelsBound     bool    `json:"labels_bound"`
}
type updateBuffer struct {
	data      []byte
	truncated bool
}

func (b *updateBuffer) Write(p []byte) (int, error) {
	n := len(p)
	remaining := (2 << 20) - len(b.data)
	if len(p) > remaining {
		p = p[:remaining]
		b.truncated = true
	}
	b.data = append(b.data, p...)
	return n, nil
}
func updateObserved(ctx context.Context, c *sql.Conn, index int) (result sql.Result, err error) {
	dir := os.Getenv("UPDATE_WAIT_DIR")
	if dir == "" {
		return c.ExecContext(ctx, "UPDATE fork_probe SET v=-1 WHERE id=1")
	}
	meta := updateMeta{Child: index, Artificial: os.Getenv("UPDATE_WAIT_ARTIFICIAL") == "1", ThresholdMS: 100}
	start := time.Now()
	stop := make(chan struct{})
	joined := make(chan error, 1)
	var returned atomic.Bool
	captured := false
	pprof.Do(ctx, pprof.Labels("operation", "update", "role", "client"), func(ctx context.Context) {
		go func() {
			timer := time.NewTimer(100 * time.Millisecond)
			defer timer.Stop()
			select {
			case <-stop:
				joined <- nil
				return
			case <-timer.C:
			}
			if returned.Load() || !updateCaptures.CompareAndSwap(0, 1) {
				joined <- nil
				return
			}
			captured = true
			meta.SnapshotBeginMS = ms(time.Since(start))
			var buf updateBuffer
			captureErr := pprof.Lookup("goroutine").WriteTo(&buf, 1)
			meta.SnapshotEndMS = ms(time.Since(start))
			meta.Bytes = len(buf.data)
			meta.Truncated = buf.truncated
			// Require actual runtime labels on a guest execution stack, not just the observer/client.
			meta.LabelsBound = hasGuestLabel(buf.data, fmt.Sprint(index))
			if captureErr == nil {
				captureErr = os.WriteFile(filepath.Join(dir, fmt.Sprintf("child-%03d.txt", index)), buf.data, 0600)
			}
			joined <- captureErr
		}()
		if meta.Artificial {
			time.Sleep(200 * time.Millisecond)
		}
		meta.ExecEnterMS = ms(time.Since(start))
		result, err = c.ExecContext(ctx, "UPDATE fork_probe SET v=-1 WHERE id=1")
		meta.ExecReturnMS = ms(time.Since(start))
		returned.Store(true)
	})
	close(stop)
	err = errors.Join(err, <-joined)
	if captured {
		meta.InsideExec = profileInsideExec(meta)
		data, e := json.MarshalIndent(meta, "", "  ")
		err = errors.Join(err, e)
		if e == nil {
			err = errors.Join(err, os.WriteFile(filepath.Join(dir, fmt.Sprintf("child-%03d.json", index)), append(data, '\n'), 0600))
		}
	}
	return
}

func hasGuestLabel(data []byte, id string) bool {
	for _, group := range strings.Split(string(data), "\n\n") {
		lines := strings.Split(group, "\n")
		matching := false
		for _, line := range lines {
			if strings.HasPrefix(line, "# labels: ") {
				var labels map[string]string
				if json.Unmarshal([]byte(strings.TrimPrefix(line, "# labels: ")), &labels) == nil && labels["child"] == id {
					matching = true
				}
			}
		}
		if matching && strings.Contains(group, "internal/generatedgo/code/p") {
			return true
		}
	}
	return false
}

func profileInsideExec(m updateMeta) bool {
	return m.ExecEnterMS > 0 && m.SnapshotBeginMS >= m.ExecEnterMS && m.SnapshotEndMS >= m.SnapshotBeginMS && m.SnapshotEndMS <= m.ExecReturnMS
}
