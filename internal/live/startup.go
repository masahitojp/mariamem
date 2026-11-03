package live

import (
	"context"
	"time"

	"github.com/masahitojp/mariamem/internal/disposal"
	"github.com/masahitojp/mariamem/internal/forklimit"
)

// RetainStartup supplies a cleanup-only child on failed allocation. Endpoint
// keeps it after a failed cleanup so explicit Reset can retry before reserving.
func RetainStartup(cause error, lease *forklimit.Lease, shutdown time.Duration) Child {
	if len(disposal.Owners(cause)) == 0 {
		return nil
	}
	return &failedStartup{cause: cause, lease: lease, shutdown: shutdown}
}

type failedStartup struct {
	cause    error
	lease    *forklimit.Lease
	shutdown time.Duration
}

func (c *failedStartup) Address() string                        { return "" }
func (c *failedStartup) Capacity() int                          { return 0 }
func (c *failedStartup) Failure() error                         { return c.cause }
func (c *failedStartup) WaitDisconnected(context.Context) error { return nil }
func (c *failedStartup) Close() error {
	ctx, cancel := context.WithTimeout(context.Background(), c.shutdown)
	defer cancel()
	err := disposal.Retry(ctx, c.cause)
	if err == nil {
		c.lease.Settle(nil)
	}
	return err
}
