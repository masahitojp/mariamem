package base

// workerFailure is configured before execution and shared by all Module copies.
// A fatal guest worker failure cancels cooperative waits, not arbitrary Go code.
type workerFailure struct {
	done   chan struct{}
	notify func(any)
}

// NotifyWorkerFailure must be installed before the root can launch workers.
// notify runs once on the failing worker and must not wait for guest completion.
// Joining and resource ownership remain the caller's separate responsibility.
func (p *ThreadPool) NotifyWorkerFailure(notify func(any)) {
	p.trapMu.Lock()
	defer p.trapMu.Unlock()
	if p.failure != nil || p.nextTID.Load() != 0 || p.trap != nil {
		panic("worker failure notification installed after execution")
	}
	p.failure = &workerFailure{done: make(chan struct{}), notify: notify}
}

func (p *ThreadPool) recordTrap(cause any) {
	p.trapMu.Lock()
	first := p.trap == nil
	if first {
		p.trap = cause
	}
	failure := p.failure
	p.trapMu.Unlock()
	if first && failure != nil {
		close(failure.done)
		if failure.notify != nil {
			failure.notify(cause)
		}
	}
}

func (p *ThreadPool) failureDone() <-chan struct{} {
	if p.failure == nil {
		return nil
	}
	return p.failure.done
}

func (p *ThreadPool) trapIfFailed() {
	select {
	case <-p.failureDone():
		p.trapMu.Lock()
		cause := p.trap
		p.trapMu.Unlock()
		panic(cause)
	default:
	}
}
