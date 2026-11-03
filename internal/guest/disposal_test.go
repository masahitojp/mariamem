package guest

import (
	"context"
	"errors"
	"io"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/disposal"
)

func TestFailedGreetingRetainsLateJoinedOwnerWithNilProcess(t *testing.T) {
	childIn, in := io.Pipe()
	out, childOut := io.Pipe()
	completed := make(chan error, 1)
	defer childIn.Close()
	defer childOut.Close()
	defer func() {
		select {
		case completed <- nil:
		default:
		}
	}()
	go func() { _, _ = childOut.Write([]byte{0, 0, 0, 0}) }()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	p, err := connectWithFailure(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, io.Discard, nil, time.Millisecond)
	if p != nil {
		t.Fatal("failed startup became a usable Process")
	}
	var detail *diagnostic.Error
	if !errors.As(err, &detail) || detail.Code != "guest_connection" || detail.Stage != "guest_ready" || !strings.Contains(err.Error(), "invalid guest frame") {
		t.Fatal("lost original diagnostics", err)
	}
	owners := disposal.Owners(err)
	if len(owners) != 1 || owners[0].Complete() {
		t.Fatal("lost unjoined Process", err)
	}
	probe, stop := context.WithCancel(context.Background())
	stop()
	if e := disposal.Retry(probe, err); !errors.Is(e, context.Canceled) {
		t.Fatal(e)
	}
	completed <- nil
	if e := disposal.Retry(ctx, err); e != nil {
		t.Fatal(e)
	}
	if !owners[0].Complete() || !strings.Contains(err.Error(), "invalid guest frame") {
		t.Fatal("rewrote failed startup")
	}
}
