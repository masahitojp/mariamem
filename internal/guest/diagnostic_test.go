package guest

import (
	"context"
	"errors"
	"github.com/masahitojp/mariamem/internal/diagnostic"
	"io"
	"strings"
	"testing"
	"time"
)

func TestCompiledIdentityFailure(t *testing.T) {
	_, err := startLinked(context.Background(), "wrong-identity", "", "", io.Discard)
	if err == nil || !strings.Contains(err.Error(), "identity mismatch") {
		t.Fatal(err)
	}
}
func TestStartupCauseAndBoundedTail(t *testing.T) {
	tail := &stderrTail{}
	tail.Write([]byte(strings.Repeat("x", 4096)))
	err := startupError(context.DeadlineExceeded, tail)
	if !errors.Is(err, context.DeadlineExceeded) || len(err.Error()) > 1600 {
		t.Fatalf("unbounded/lost cause: %v", err)
	}
}

// Removing executable startup must retain controlled greeting/protocol errors.
func TestFramedStartupFailureSurvivesAndJoins(t *testing.T) {
	childIn, in := io.Pipe()
	out, childOut := io.Pipe()
	completed := make(chan error, 1)
	go func() {
		// Zero-length framing is invalid; the host must return an error and join.
		_, err := childOut.Write([]byte{0, 0, 0, 0})
		childIn.Close()
		childOut.Close()
		completed <- err
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err := Connect(ctx, in, out, completed, nil, io.Discard)
	var detail *diagnostic.Error
	if !errors.As(err, &detail) || detail.Code != "guest_connection" || detail.Stage != "guest_ready" || !strings.Contains(err.Error(), "invalid guest frame") {
		t.Fatal(err)
	}
}
