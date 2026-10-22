package diagnostic

import (
	"context"
	"errors"
	"fmt"
	"testing"
)

func TestControlCodeDistinguishesInvalidationFromRequestDeadline(t *testing.T) {
	for _, cause := range []error{context.Canceled, context.DeadlineExceeded} {
		for _, wrap := range []func(error) error{func(e error) error { return e }, func(e error) error { return fmt.Errorf("outer context: %w", e) }} {
			invalid := wrap(Wrap("unusable", "host_control", cause))
			if !errors.Is(invalid, cause) {
				t.Fatal("cause lost")
			}
			if code := ControlCode(invalid, "unusable"); code != "unusable" {
				t.Fatal("invalidated DB misclassified", code)
			}
			for _, request := range []error{wrap(cause), wrap(Wrap("host_start", "startup", cause))} {
				if code := ControlCode(request, "host_start"); code != "timeout" {
					t.Fatal("request timeout changed", code)
				}
			}
		}
	}
	for _, code := range []string{"unusable", "busy", "closed", "guest_connection"} {
		if got := ControlCode(errors.New("ordinary failure"), code); got != code {
			t.Fatal("unrelated classification changed", got)
		}
	}
}
