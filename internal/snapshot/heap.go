package snapshot

import (
	"context"
	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/timing"
)

// OwnHeap strictly verifies a legacy digest-bearing Heap for its direct callers.
// Current callers are tests; normal capture uses FreezeRoot/TakeRoot/OwnRoot.
// These strict oracles do not validate the normal capture wiring.
func OwnHeap(h *prepared.Heap, build string) (*Owned, error) {
	_, finish := timing.Begin(context.Background(), "snapshot_own")
	defer finish()
	if e := h.Verify(build); e != nil {
		return nil, e
	}
	return &Owned{heap: h}, nil
}
