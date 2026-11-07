package host

import (
	"context"
	"github.com/masahitojp/mariamem/internal/snapshot"
	"io"
	"time"
)

// Start is the private public-entry factory. Canonical source keeps its existing
// runtime; checked experiment staging substitutes this one file explicitly.
func Start(ctx context.Context, restore *snapshot.Owned, timeout time.Duration, stderr io.Writer) (Service, error) {
	s, e := StartGenerated(ctx, restore, timeout, stderr)
	if e != nil {
		return nil, e
	}
	return s, nil
}
