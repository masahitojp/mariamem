# Go usage

Use `v0.6.2` on a [supported platform](../README.md#installation).
Start with the [README test](../README.md#go), then prepare schema and seed
once with `mariamemtest` as shown below.

## Prepare once, Fork independent databases

Put migrations and seed SQL in `Prepare`, then request `fixture.DB(t)` in each
test. A nil `Prepare` uses an empty baseline. The complete example includes two
ordinary tests and bounded parallel subtests. Save it as `items_test.go` in a
new package:

```go
package example_test

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
			// Migration commands can use ctx and dsn. Return their original
			// error, retain stderr and never log a DSN containing credentials.
			if _, err := db.ExecContext(ctx,
				"CREATE TABLE items (id INT PRIMARY KEY, label VARCHAR(32)) ENGINE=InnoDB"); err != nil {
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

func TestParallelSeeds(t *testing.T) {
	for _, name := range []string{"first", "second", "third", "fourth"} {
		t.Run(name, func(t *testing.T) {
			t.Parallel()
			db := fixture.DB(t)
			if _, err := db.ExecContext(t.Context(), "INSERT INTO items VALUES (2, 'own')"); err != nil {
				t.Fatal(err)
			}
			var count int
			if err := db.QueryRowContext(t.Context(), "SELECT COUNT(*) FROM items").Scan(&count); err != nil {
				t.Fatal(err)
			}
			if count != 2 {
				t.Fatalf("count = %d, want seed plus this child's insert", count)
			}
		})
	}
}
```

Run `go test ./...`. `TestCommit` and `TestSeed` see the same seed in either order; committed
mutations and ordinary assertion failures do not become the next test's data.
`Run` invokes preparation once in this package process, runs the suite and closes
the fixture before returning its exit code to `os.Exit`. Preparation failures
skip the suite; final cleanup failure changes an otherwise successful exit to1.
Repeated `DB(t)` in one test returns that test's pool. Another test/subtest gets
another child. Do not close the supplied pool manually; the helper registers
cleanup in pool-before-child order.

Your callback may use the supplied `db` or pass `dsn` to a migration command.
Return the original error, finish transactions and retire any additional pools
or processes before returning. The helper closes its preparation pool and waits
for physical disconnect before capture. It cannot find unregistered application
work or force noncooperative callbacks to stop.

### Sequential and parallel cases

Ordinary tests run sequentially. `TestParallelSeeds` in the complete example
uses testing subtests and calls `t.Parallel()` before `DB(t)`.

`MaxForks: 2` bounds admitted child lifecycles per fixture. Run with
`go test -parallel 4 ./...` to allow four scheduled parallel tests while that
fixture still admits at most two children at a time. The parent does not acquire
a DB while waiting for subtests. Other packages/processes and additional
fixtures have independent budgets and baselines; this is not a global resource
cap or a throughput promise. No goroutine join or manual child cleanup is needed
for these testing subtests.

For helper timeouts, admission failures, cleanup debt and explicit fixture
ownership with `New`, see [prepared Go fixtures](go-prepared-fixture.md).

## Low-level database lifetimes

### Start fresh

Use `mariamem.Start(ctx, mariamem.Options{})` when you need a Fresh database
outside the test helper. Open a driver pool using its DSN, then close statements
and pools before the database. For a manual prepared lifecycle, commit and close
preparation connections, call `WaitDisconnected`, capture with `Snapshot`, and
close each Fork before releasing the baseline. Successful capture consumes the
source. These APIs remain available; ordinary tests above delegate ownership
to `mariamemtest`.

When application code accepts `*sql.DB`, pass `fixture.DB(t)` through that
construction seam, including to GORM's MySQL configuration. Keep distinct pools
for distinct children; never switch an existing pool to another endpoint. An
application-created pool remains application-owned and must close before its
child; the helper cannot automatically enroll it. Its supplied pools use real
prepared execution (`InterpolateParams=false`). Python's opt-in
[routing](connection-routing.md) is a separate integration.

<a id="same-process-connections-unreleased"></a>

## Same-process connections

Since 0.6.2, Go callers can select same-process MySQL wire connections.

TCP remains the default. For Go-owned pools, opt in to `net.Pipe` with
`mariamemtest.Options{InProcess: true}`. This selects Pipe for the helper's
preparation and per-test pools. The `Prepare` callback's DSN still targets TCP,
so an external migration command can use it normally. No Node/Python connection
routing, global driver registration or listener-free startup is implied.

For a low-level `Database` returned by Start or Fork, assign its method to the
normal MySQL connector. The following is a function-body excerpt: `db` is that
live `*mariamem.Database`, and the enclosing function returns an error. Import
`database/sql` and `mysql "github.com/go-sql-driver/mysql"`; close the
pool before the owning database. For a complete test file, use the helper
example [above](#prepare-once-fork-independent-databases) and add `InProcess: true` to its keyed Options literal:

```go
config, err := mysql.ParseDSN(db.DSN())
if err != nil {
    return err
}
config.DialFunc = db.DialContext
connector, err := mysql.NewConnector(config)
if err != nil {
    return err
}
pool := sql.OpenDB(connector)
defer pool.Close() // Before closing/capturing the owning database.
```

The connector stays bound to that specific Database. It accepts only `tcp` or
`tcp4` and the exact endpoint from that Database's DSN; it never redirects an
unrelated endpoint. Database name and normal driver settings still apply.
`DSN()` keeps its existing interpolation setting; select
`config.InterpolateParams = false` for real prepared parameter execution.

The same handshake, wire handlers, session slots and guest serve both transports.
A full local Pipe admission returns a `HostError` matching `ErrCapacity` before
starting a worker; TCP keeps its existing MySQL1040 response. Closed/consumed
owners match `ErrClosed`, and failed instances match `ErrUnusable`. A cancelled
Dial context is rejected; after Dial returns, the driver controls handshake/query
cancellation and I/O deadlines. Query interruption retains instance invalidation
and cooperative cleanup semantics.

Close every connection/pool and call `WaitDisconnected` before Snapshot capture.
A raw pipe awaiting handshake is busy and prevents capture. Forked databases
require their own connector/DialContext. Closing one child does not close its
siblings. Live's stable public endpoint continues to use TCP; do not reuse a
consumed Database's dialer for another owner. This opt-in reduces TCP overhead,
not SQL/wire work, and adds no compatibility or performance guarantee.

## Development and compatibility

Install the published module and optional release audit files with:

```sh
go get github.com/masahitojp/mariamem@v0.6.2
gh release download v0.6.2 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.6.2-corresponding-source.tar.gz'
```

Runtime details belong in [architecture](v04-generated-go-architecture.md).
See [local verification](development.md#local-verification) for scoped
development checks, [release notes](../release/NOTES-v0.6.2.md)
and [API migration](changes-since-v050.md).
The full generated guest is not
Go race-detector clean; focused checks do not establish general race cleanliness.

Since 0.6.0, the package supports stable Live endpoints across sequential browser E2E
cases. Use independent Forks for concurrent cases; Live does not promise a
parallel shared mutable endpoint. See the [Live guide](live.md) for connection
draining and reset ownership.

## Owned E2E entry

The [owned E2E examples](examples/e2e_owned/README.md) demonstrate
application-specific preparation/start/quiescence/stop hooks over Live. This
entry was approved for bounded main adoption with the supplied hook obligations;
it is available since 0.6.0. Existing direct Live APIs remain the mechanism
underneath the entry. See the [integration receipt](reviews/e2e-integration-ci-41095184074/assessment.json)
for exact tested source/profiles. Arbitrary unregistered work and non-cooperative
shutdown remain outside the guarantee; detailed resource characterization is deferred.

<a id="per-snapshot-fork-limits"></a>
<a id="in-memory-baseline-lifetime"></a>
<a id="lifecycle-cancellation-and-errors"></a>
<a id="wire-scope"></a>
<a id="wire-scope-for-current-source-builds"></a>

## Reference

- [Snapshot ownership, Fork limits, cancellation and errors](go-reference.md)
- [SQL, driver exceptions and wire limits](compatibility.md)

### Process-local initialization image (v0.7.0 candidate)

The implementation is adopted on main and unreleased. See the
[initialization-image ownership reference](go-reference.md#process-local-initialization-image-unreleased)
for lifetime, sharing and failure behavior.
