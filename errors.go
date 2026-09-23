package mariamem

import (
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/host"
)

var (
	ErrBusy              = errors.New("database is busy")
	ErrTransactionActive = errors.New("transaction is active")
	ErrClosed            = errors.New("database or snapshot is closed")
)

// HostError preserves the underlying error and whether the source DB was consumed.
type HostError struct {
	Code   string
	Closed bool
	Err    error
}

func (e *HostError) Error() string { return fmt.Sprintf("mariamem %s: %v", e.Code, e.Err) }
func (e *HostError) Unwrap() error { return e.Err }
func (e *HostError) Is(target error) bool {
	return (e.Code == "busy" && target == ErrBusy) || (e.Code == "transaction_active" && target == ErrTransactionActive) || (e.Code == "closed" && target == ErrClosed)
}
func hostError(err error, code string, closed bool) error {
	if err == nil {
		return nil
	}
	var rejected *host.Rejected
	if errors.As(err, &rejected) {
		code = rejected.Code
	}
	return &HostError{Code: code, Closed: closed, Err: err}
}
