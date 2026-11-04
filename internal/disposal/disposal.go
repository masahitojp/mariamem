// Package disposal carries private cleanup ownership separately from an
// operation's error. A failed operation remains failed after cleanup succeeds.
package disposal

import (
	"context"
	"errors"
	"fmt"
	"os"
	"sync"
)

var ErrPending = errors.New("disposal is not yet complete")

// Owner serializes retries and confirms completion exactly once. A callback
// must preserve its resources on failure and return nil only after disposal.
// Waiting callbacks honor ctx; already joined cleanup may finish with a canceled
// context. Filesystem operations retain their existing synchronous semantics.
type Owner struct {
	gate         chan struct{}
	done         chan struct{}
	continueOnce sync.Once
	cleanup      func(context.Context) error
}

func New(cleanup func(context.Context) error) *Owner {
	return &Owner{gate: make(chan struct{}, 1), done: make(chan struct{}), cleanup: cleanup}
}

func (o *Owner) Done() <-chan struct{} { return o.done }
func (o *Owner) Complete() bool {
	select {
	case <-o.done:
		return true
	default:
		return false
	}
}

func (o *Owner) Retry(ctx context.Context) error {
	if o.Complete() {
		return nil
	}
	// Prefer an available gate even for a probe's already canceled context.
	select {
	case o.gate <- struct{}{}:
	default:
		select {
		case <-o.done:
			return nil
		case o.gate <- struct{}{}:
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	defer func() { <-o.gate }()
	if o.Complete() {
		return nil
	}
	if err := o.cleanup(ctx); err != nil {
		return err
	}
	o.cleanup = nil
	close(o.done)
	return nil
}

// Probe performs ready cleanup without waiting. Its internal canceled context
// must not masquerade as cancellation of the user's operation/control request.
func (o *Owner) Probe() error {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	err := o.Retry(ctx)
	if errors.Is(err, context.Canceled) {
		return ErrPending
	}
	return err
}

// Continue retains one owner through late completion even if an ordinary Start
// caller drops its error. It attempts cleanup once, not an unbounded retry loop.
// A filesystem failure keeps the typed owner available for an explicit retry.
func (o *Owner) Continue() {
	o.continueOnce.Do(func() { go func() { _ = o.Retry(context.Background()) }() })
}

type pending struct {
	cause, cleanup error
	owner          *Owner
}

func (e *pending) Error() string {
	if e.cause == nil {
		return fmt.Sprintf("cleanup incomplete: %v", e.cleanup)
	}
	return fmt.Sprintf("%v; cleanup incomplete: %v", e.cause, e.cleanup)
}
func (e *pending) Unwrap() error { return errors.Join(e.cause, e.cleanup) }

// Retain attaches an unresolved owner without hiding the original error.
// It is internal host bookkeeping, never a serialized/public cleanup handle.
func Retain(cause, cleanup error, owner *Owner) error {
	owner.Continue()
	return &pending{cause: cause, cleanup: cleanup, owner: owner}
}

// Owners follows wrappers and joins. A parent owner already owns the cleanup
// dependencies in its cause, so those are not retried independently here.
func Owners(err error) []*Owner {
	var owners []*Owner
	seen := make(map[*Owner]bool)
	var visit func(error)
	visit = func(err error) {
		if err == nil {
			return
		}
		if e, ok := err.(*pending); ok {
			if !seen[e.owner] {
				seen[e.owner] = true
				owners = append(owners, e.owner)
			}
			return
		}
		switch e := err.(type) {
		case interface{ Unwrap() []error }:
			for _, child := range e.Unwrap() {
				visit(child)
			}
		case interface{ Unwrap() error }:
			visit(e.Unwrap())
		}
	}
	visit(err)
	return owners
}

func Retry(ctx context.Context, err error) error {
	var result error
	for _, owner := range Owners(err) {
		result = errors.Join(result, owner.Retry(ctx))
	}
	return result
}

// Wait joins execution without confusing its failed operation with live resource
// ownership. Check completion before ctx so a nonblocking probe can confirm it.
func Wait(ctx context.Context, joined <-chan struct{}) error {
	select {
	case <-joined:
		return nil
	default:
	}
	select {
	case <-joined:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// After runs cleanup only after every retained dependency is disposed. Its first
// attempt does not wait for running execution. A late completion is owned by one
// continuation; failed removal is observable and retryable through the result.
func After(cause error, cleanup func() error) error {
	return after(cause, cleanup, true)
}

// CleanupAfter reports only cleanup failure, for APIs that store a Close result
// separately from the failed operation. The owner still retains its dependencies.
func CleanupAfter(dependency error, cleanup func() error) error {
	return after(dependency, cleanup, false)
}

func after(cause error, cleanup func() error, keepCause bool) error {
	owner := New(func(ctx context.Context) error {
		if err := Retry(ctx, cause); err != nil {
			return err
		}
		return cleanup()
	})
	var reported error
	if keepCause {
		reported = cause
	}
	if err := owner.Probe(); err != nil {
		return Retain(reported, err, owner)
	}
	return reported
}

func RemoveAfter(cause error, path string) error {
	return After(cause, func() error { return os.RemoveAll(path) })
}
