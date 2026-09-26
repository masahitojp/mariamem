package mariamem

import (
	"errors"
	"fmt"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/host"
)

// These errors identify common rejected operations; use errors.Is to test them.
var (
	ErrBusy              = errors.New("database is busy")
	ErrTransactionActive = errors.New("transaction is active")
	ErrClosed            = errors.New("database or snapshot is closed")
	ErrUnusable          = errors.New("database instance is no longer usable")
)

// HostError preserves the underlying error and whether the source DB was consumed.
// Startup Code values include unsupported_platform, native_unavailable,
// artifact_mismatch, guest_start, guest_connection, and host_start. Stage names
// identify the failed boundary for diagnosis; they are not an execution API.
// Runtime invalidation uses unusable; ordinary SQL errors remain driver errors.
type HostError struct {
	Code   string
	Stage  string // Startup boundary, when available; empty for ordinary lifecycle errors.
	Closed bool
	Err    error
}

func (e *HostError) Error() string { return fmt.Sprintf("mariamem %s: %v", e.Code, e.Err) }
func (e *HostError) Unwrap() error { return e.Err }
func (e *HostError) Is(target error) bool {
	return (e.Code == "busy" && target == ErrBusy) || (e.Code == "transaction_active" && target == ErrTransactionActive) || (e.Code == "closed" && target == ErrClosed) || (e.Code == "unusable" && target == ErrUnusable)
}
func hostError(err error, code string, closed bool) error {
	if err == nil {
		return nil
	}
	var rejected *host.Rejected
	if errors.As(err, &rejected) {
		code = rejected.Code
	}
	var detail *diagnostic.Error
	stage := ""
	if errors.As(err, &detail) && (code == "artifacts" || code == "start") {
		code, stage = detail.Code, detail.Stage
	}
	return &HostError{Code: code, Stage: stage, Closed: closed, Err: err}
}
