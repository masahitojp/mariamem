package diagnostic

import (
	"context"
	"errors"
)

// ControlCode preserves explicit DB invalidation even when its retained cause
// is a deadline. A request cancellation by itself is still a timeout, which
// does not mean all databases in a shared host were invalidated.
func ControlCode(err error, code string) string {
	var detail *Error
	if (errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded)) &&
		(!errors.As(err, &detail) || detail.Code != "unusable") {
		return "timeout"
	}
	return code
}
