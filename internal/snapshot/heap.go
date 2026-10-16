package snapshot

import (
	"context"
	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/timing"
)

// OwnHeap performs the third complete verification on the exact immutable
// backing used by Fork. A borrowed producer/path/unchecked boolean is not owned.
func OwnHeap(h *prepared.Heap, build string) (*Owned, error) {
	_, finish := timing.Begin(context.Background(), "snapshot_own")
	defer finish()
	if e := h.Verify(build); e != nil {
		return nil, e
	}
	return &Owned{heap: h}, nil
}
