// Caller-only experiment instrumentation; no SQL batching, runtime or guest change.
package store

import (
	"context"
	"database/sql"
	"time"
)

type SampleOperation struct {
	Phase      string `json:"phase"`
	OrderID    int64  `json:"order_id"`
	ProductID  int64  `json:"product_id"`
	BeginUS    int64  `json:"begin_us"`
	DurationUS int64  `json:"duration_us"`
	Error      string `json:"error,omitempty"`
}
type SampleRecord struct {
	DBID      string             `json:"db_id"`
	Lane      string             `json:"lane"`
	StartUS   int64              `json:"start_us"`
	TotalUS   int64              `json:"total_us"`
	Durations map[string][]int64 `json:"durations_us"`
	Long      []SampleOperation  `json:"operations_ge50ms"`
	origin    time.Time
	emit      func(*SampleRecord)
	observer  *sampleObserver
}
type sampleObserverKey struct{}
type sampleObserver struct {
	lane  string
	dbID  string
	clock func() int64
	emit  func(*SampleRecord)
}

func WithSampleObserver(ctx context.Context, lane string, dbID string, clock func() int64, emit func(*SampleRecord)) context.Context {
	return context.WithValue(ctx, sampleObserverKey{}, sampleObserver{lane, dbID, clock, emit})
}
func newSampleRecord(ctx context.Context) *SampleRecord {
	o, ok := ctx.Value(sampleObserverKey{}).(sampleObserver)
	if !ok {
		return nil
	}
	return &SampleRecord{DBID: o.dbID, observer: &o, Lane: o.lane, StartUS: o.clock(), Durations: map[string][]int64{}, origin: time.Now(), emit: o.emit}
}
func (r *SampleRecord) measure(phase string, order, product int64, f func() error) error {
	if r == nil {
		return f()
	}
	at := time.Now()
	offset := time.Since(r.origin).Microseconds()
	var stop func()
	if phase == "prepare" {
		stop = startPrepareCapture(r.observer, phase, len(r.Durations[phase])+1)
	}
	e := f()
	if stop != nil {
		stop()
	}
	duration := time.Since(at).Microseconds()
	r.Durations[phase] = append(r.Durations[phase], duration)
	if duration >= 50000 {
		v := SampleOperation{Phase: phase, OrderID: order, ProductID: product, BeginUS: r.StartUS + offset, DurationUS: duration}
		if e != nil && e != sql.ErrTxDone {
			v.Error = e.Error()
		}
		r.Long = append(r.Long, v)
	}
	return e
}
func (r *SampleRecord) finish() {
	if r == nil {
		return
	}
	r.TotalUS = time.Since(r.origin).Microseconds()
	r.emit(r)
}
