package probe

import (
	"context"
	"errors"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

type waveKey struct{}
type rendezvous struct {
	count atomic.Int32
	size  int32
	done  chan struct{}
	last  func()
}

func newRendezvous(n int, last func()) *rendezvous {
	return &rendezvous{size: int32(n), done: make(chan struct{}), last: last}
}
func (b *rendezvous) wait(ctx context.Context) error {
	if b.count.Add(1) == b.size {
		if b.last != nil {
			b.last()
		}
		close(b.done)
	}
	select {
	case <-b.done:
		return ctx.Err()
	case <-ctx.Done():
		return ctx.Err()
	}
}

type waveGate struct{ start, ready *rendezvous }
type Wave struct {
	Index      int     `json:"index"`
	Begin      float64 `json:"begin_ms"`
	ForksBegin float64 `json:"forks_begin_ms"`
	AllReady   float64 `json:"all_ready_ms"`
	End        float64 `json:"end_ms"`
	ForkCPU    float64 `json:"fork_cpu_ms"`
}

func fixedWaveBatch(ctx context.Context, r *Report, start func(context.Context) (*Database, error), sn *Snapshot, cancel context.CancelFunc) (err error) {
	at := time.Now()
	r.BatchBegin = ms(at.Sub(r.origin))
	batchCPU := clock()
	for baseIndex := 0; baseIndex < r.Count; baseIndex += r.Parallel {
		if ctx.Err() != nil {
			err = errors.Join(err, ctx.Err())
			break
		}
		w := Wave{Index: baseIndex / r.Parallel, Begin: ms(time.Since(r.origin))}
		var forkCPU int64
		gate := &waveGate{start: newRendezvous(r.Parallel, func() { w.ForksBegin = ms(time.Since(r.origin)); forkCPU = cpu(clock()) }), ready: newRendezvous(r.Parallel, func() { w.AllReady = ms(time.Since(r.origin)); w.ForkCPU = float64(cpu(clock())-forkCPU) / 1e6 })}
		results := make(chan Sample, r.Parallel)
		var wg sync.WaitGroup
		for lane := 0; lane < r.Parallel; lane++ {
			wg.Add(1)
			go func(lane, index int) {
				defer wg.Done()
				s, e := one(context.WithValue(ctx, waveKey{}, gate), r, lane, index, start, sn)
				if e != nil && s.Error == "" {
					s.Error = e.Error()
				} // Preserve every error; join peers before cancellation.
				results <- s
			}(lane, baseIndex+lane)
		}
		wg.Wait()
		close(results)
		w.End = ms(time.Since(r.origin))
		r.Waves = append(r.Waves, w)
		for s := range results {
			r.Samples = append(r.Samples, s)
			if s.Error != "" {
				err = errors.Join(err, errors.New(s.Error))
			}
		}
		if err != nil {
			cancel()
			break
		}
	}
	r.BatchEnd = ms(time.Since(r.origin))
	r.Batch = r.BatchEnd - r.BatchBegin
	r.BatchCPU = float64(cpu(clock())-cpu(batchCPU)) / 1e6
	r.MaxActive = int32(r.Parallel)
	sort.Slice(r.Samples, func(i, j int) bool { return r.Samples[i].Index < r.Samples[j].Index })
	if err == nil && len(r.Samples) != r.Count {
		err = errors.New("incomplete fixed waves")
	}
	return
}
