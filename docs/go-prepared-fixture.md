# Prepared Go tests — unreleased candidate

This candidate adds `github.com/masahitojp/mariamem/mariamemtest`. It is not part
of published v0.5.3. The helper owns preparation, capture, child pools and cleanup;
your callback owns the migration/seed instructions and their success signal.

```go
package app_test

import (
	"context"
	"database/sql"
	"os"
	"testing"

	"github.com/masahitojp/mariamem/mariamemtest"
)

var fixture *mariamemtest.Fixture

func TestMain(m *testing.M) {
	os.Exit(mariamemtest.Run(m, mariamemtest.Options{
		Prepare: func(ctx context.Context, db *sql.DB, dsn string) error {
			// Migration commands can run here with ctx and dsn. Return the
			// original command error and retain stderr; never log a secret DSN.
			if _, err := db.ExecContext(ctx,
				"CREATE TABLE items (id INT PRIMARY KEY, label VARCHAR(32))"); err != nil {
				return err
			}
			_, err := db.ExecContext(ctx, "INSERT INTO items VALUES (1, 'seed')")
			return err
		},
		MaxForks: 2,
	}, func(f *mariamemtest.Fixture) { fixture = f }))
}

func TestCommit(t *testing.T) {
	db := fixture.DB(t)
	if _, err := db.ExecContext(t.Context(), "DELETE FROM items"); err != nil {
		t.Fatal(err)
	}
}

func TestSeed(t *testing.T) {
	db := fixture.DB(t)
	var label string
	if err := db.QueryRowContext(t.Context(),
		"SELECT label FROM items WHERE id=1").Scan(&label); err != nil {
		t.Fatal(err)
	}
	if label != "seed" {
		t.Fatalf("starting label: %q", label)
	}
}
```

Both tests start from the declared schema/seed in either order, including after a
previous test commits or fails. Preparation runs once per fixture in this test
package process. Other packages/processes have their own baselines. A nil Prepare
explicitly selects an empty baseline. Nothing persists between `go test` runs.

The helper closes its preparation pool and waits for physical disconnect before
capture; retire any pools/connections opened by your callback or migration tool.
There is no implicit rollback, retry or original-database fallback. Child pools
use normal driver prepared execution, max-open2/max-idle1; preparation uses
max-open1. Arbitrary caller-created pools are outside those budgets.

Repeated `fixture.DB(t)` returns the same test-owned pool. A distinct subtest gets
a distinct child. Call `t.Parallel()` **before** requesting DB. MaxForks defaults
to2 per fixture and counts child startup and unreclaimed owners, not only running
test bodies. `go test -parallel` limits scheduling; `-p` and multiple fixtures can
multiply the DB budget. Do not hold a parent's child while waiting for nested
children at capacity. Admission times out with an actionable error rather than
borrowing another test's DB. OperationTimeout defaults to120s and covers setup
and each acquisition; it is cooperative, not a forced callback/guest kill.

`DB(t)` registers pool-before-child cleanup. `Fixture.Close()` stops admission,
actively ends all helper-owned handles and then closes the baseline; it does not
wait for future `t.Cleanup` callbacks. Calls are idempotent. For ownership outside
TestMain use `New(ctx, options)` and check `Close()` yourself. Underlying shutdown
uses its own lifetime; canceled test contexts do not skip cleanup. Hard kills,
noncooperative work and unregistered external pools are not automatically reaped.

Helper setup/acquisition errors explain the stage, preserved original failure,
cleanup state and a next action (or an unknown underlying cause). `errors.Is` and
`errors.As` can inspect both original and cleanup errors, including MySQL errno
and SQLSTATE. Ordinary test assertions and SQL calls keep their normal output.
After a capture failure, successful helper-owner finalization is reported
separately from unverified capture-internal cleanup; inspect the original error
for backing-release details. A generic capture error does not imply a busy DB.
Cleanup errors are reported even when the test already failed. `Run` skips the
suite on failed setup, preserves a nonzero suite exit code and changes a zero
exit to1 when final cleanup fails. It does not retry failed work.

This is the first implementation checkpoint. Both-host runtime receipts, bounded
resource/time observations and the full G1 acceptance remain tracked in the
[implementation record](reviews/v06x-go-fixture-implementation.md); a PR or a unit
PASS alone does not complete G1 or the whole dogfood scope.
