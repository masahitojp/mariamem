package host

import (
	"context"
	"encoding/binary"
	"errors"
	"io"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/guest"
)

func TestConsumedFailureKeepsTransferUntilGuestAndWorkersJoin(t *testing.T) {
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
	go func() {
		body := []byte(`{"request_id":0,"result":{"ready":true,"api_version":2,"max_sessions":16}}`)
		_ = binary.Write(childOut, binary.LittleEndian, uint32(len(body)))
		_, _ = childOut.Write(body)
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	p, err := guest.Connect(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	transfer := filepath.Join(t.TempDir(), "transfer")
	if err := os.Mkdir(transfer, 0700); err != nil {
		t.Fatal(err)
	}
	s := &Server{Guest: p, listener: unusedListener{}, transfer: transfer}
	s.workers.Add(1)
	var release sync.Once
	defer release.Do(s.workers.Done)
	s.mu.Lock()
	s.stopAccepting()
	s.mu.Unlock()
	cause := errors.New("capture consumed but execution not joined")
	err = s.disposeAfter(cause)
	owners := disposal.Owners(err)
	if len(owners) != 1 || owners[0].Complete() {
		t.Fatal("lost cleanup owner", err)
	}
	if _, e := os.Stat(transfer); e != nil {
		t.Fatal("removed before guest join", e)
	}
	completed <- nil
	select {
	case <-p.Done():
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	if owners[0].Complete() {
		t.Fatal("disposed before worker join")
	}
	if _, e := os.Stat(transfer); e != nil {
		t.Fatal("removed before worker join", e)
	}
	release.Do(s.workers.Done)
	if e := disposal.Retry(ctx, err); e != nil {
		t.Fatal(e)
	}
	if _, e := os.Stat(transfer); !os.IsNotExist(e) {
		t.Fatal("retained joined transfer", e)
	}
	if !errors.Is(err, cause) {
		t.Fatal("original cause lost")
	}
	if again := s.disposeAfter(cause); again != cause {
		t.Fatal("cleanup state not reused", again)
	}
}
