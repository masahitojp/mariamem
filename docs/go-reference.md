# Go ownership and lifecycle reference

For your first test and preparation, start with the [Go guide](go.md).

## In-memory baseline lifetime

`Snapshot(ctx, SnapshotOptions{})` consumes a disconnected source DB and owns a
fixed baseline with private immutable blocks. Heap-backed capture seals the same
backing and checks its identity and structure, without rescanning every byte.
Content checks remain at internal import/transfer boundaries and when borrowed
file mappings are copied into owned memory.
`Fork` creates independent MariaDB execution
with private block changes. Closing the baseline prevents new Forks and waits
for admitted startups; started children remain usable until separately closed.

Snapshot content is process-local. `SnapshotOptions.Destination` and
`LoadSnapshot` are removed in this version. Re-run migrations/seed to prepare
state in each test process. No user-managed file or daemon is required.
Closing a handle releases its ownership; other children may still own blocks.
Go memory reclamation and OS RSS reduction have different timing.

### Per-Snapshot Fork limits

Since 0.6.1, Go exposes `SnapshotOptions.MaxForks` and `Snapshot.MaxForks()`.
This function-body excerpt assumes a live disconnected `source`, a caller-owned
bounded `ctx`, the `mariamem` import and an enclosing function returning an error.
Commit/close preparation pools and call `source.WaitDisconnected(ctx)` first:

```go
prepared, err := source.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 2})
if err != nil { return err }
defer prepared.Close()
child, err := prepared.Fork(ctx)
if err != nil { return err }
defer child.Close()
```

Zero selects a finite automatic limit once at capture; explicit values1 through
2,147,483,647 override it. Invalid values reject before consuming the source.
The automatic budget is one quarter of the minimum observed physical RAM,
Linux cgroup limit and Go runtime memory limit, divided by256 MiB per child;
it falls back to a finite CPU count if memory information is unavailable.
On Linux, validated `sysinfo(2)` totalram/mem_unit and `/proc/meminfo` MemTotal
observations both participate in the minimum; either source may fail without
discarding the other. Cgroup/Go memory limits still apply when physical readings
fail. CPU fallback is used only when all memory observations are unavailable.
`MaxForks()` returns the resolved number. This is a memory heuristic, not a
CPU/latency optimum or OOM guarantee. Use an explicit limit for a latency-sensitive
suite, and budget multiple baselines/processes separately.

If the container memory limit is unreadable or invisible, auto sizing can use
host RAM and admit more children than the container can afford (for example,
64 GiB host RAM can resolve to64 despite a hidden512 MiB container limit).
Set an explicit cap in that environment. Independent root `Start` / `start()`
calls are outside Snapshot caps; finite Fork defaults are not a global DB limit.

A slot counts reservation/startup, a live child and unconfirmed cleanup. Full
capacity waits before starting another MariaDB. Go's context covers waiting and
startup; an expired capacity wait returns `HostError` with code `pool_timeout`,
stage `fork_wait` and an underlying context error. Closing a child permits a
later Fork. Capacity errors include `max_forks`, observed `occupied_slots` and
"close owned children or increase max_forks". Counts include reserved/startup,
live and unconfirmed-cleanup owners; they can change after sampling. Go's
underlying context error remains available through `errors.Is`.
Closing the baseline wakes capacity waiters while existing children
remain usable. Cleanup uncertainty stops admission; later disposal alone does
not automatically resume it. Prepare a new baseline or use an explicit Live
Reset that confirms all cleanup debt. There is no unlimited Snapshot/Fork setting.

A capture failure has a stricter limit: if cleanup of its newly owned Snapshot
also fails, the shared host records permanent `captureDebt`. `Owned.Close` caches
that error and cannot retry the descriptors; the affected parent slot remains
occupied and admission stays stopped, even after runtime disposal is confirmed.
Cleanup retry and Live Reset cannot clear this capture debt. Do not reuse that
pool; safely close its remaining owners and prepare a fresh independent lineage.
This is distinct from retryable child-runtime cleanup debt described above.

Do not synchronously request another child while the same goroutine holds every
slot. Release one first, or use a context deadline/cancellation; a deferred Close
runs only after the waiting Fork returns. Use keyed option literals when upgrading:
the expanded `SnapshotOptions` / `HTTPConfig` structs require updates to positional
literals.

Finite admission shipped in 0.6.1. See the
[adoption decision](decisions/issue53-fork-limit-adoption.md) for its accepted
limits and [current release evidence](project-status.md#current-published-release)
for exact-version qualification. Historical candidate receipts retain their own SHAs.


## Lifecycle, cancellation and errors

Start's context governs startup, not the lifetime of the returned DB.
Zero startup/shutdown/query timeouts default to 120/30/30 seconds; negative
values are rejected. Close is idempotent and returns its stored cleanup result.
Endpoint information remains available after Close; it does not imply the DB
is usable.

Snapshot forwards its context without adding a default timeout. The shutdown
deadline does not make freeze/content validation context-interruptible; cleanup can
outlast it. Successful Snapshot consumes its source; precondition rejection
leaves it running. Failure after acceptance can consume it as well
(`HostError.Closed`). Use `errors.Is` with `ErrBusy`,
`ErrTransactionActive`, `ErrClosed`, and `errors.As` with `*HostError`.

SQL/driver exceptions and unsupported commands are listed in
[compatibility](compatibility.md).

Multiple SQL clients have separate sessions, transactions and temporary tables.
Current capacity is 16, not a permanent API or throughput guarantee. Excess TCP
connections receive recoverable MySQL error 1040; Go Pipe admission returns
`ErrCapacity`. Slots are reused after disconnect cleanup. Close the pool before `WaitDisconnected`.
`WaitDisconnected` observes host session cleanup; it does not close pools,
prevent new connections or complete database disposal. Stop application work
first, and use a context deadline when the caller needs a bounded wait.
The DSN enables driver-side parameter interpolation for ordinary queries.
Go explicit Prepare uses real prepared execution since 0.6.0;
interpolation is not required as a substitute for it.

Ordinary SQL errors leave the DB usable. A fatal guest
worker trap invalidates the DB promptly and retains its cause, without waiting
for the query timeout. Host query timeout, client cancellation or disconnect
during active SQL also invalidates the DB. Close it and start/fork
another rather than retrying against it. `db.Err()` matches `ErrUnusable` and
retains the cause; a host deadline also matches `context.DeadlineExceeded`.
`db.Closed()` becomes true. Forced reclamation of hung execution is not guaranteed.

`HostError.Code` identifies startup/lifecycle errors and `Stage` adds diagnostic
context; causes remain unwrap-able. Startup failures return no usable DB.
`Logs()` retains bounded diagnostics. Stage names are not a stable list of
internal mechanisms.

## Process-local initialization image (unreleased)


The adopted, unreleased implementation builds an immutable initialization image on first use and keeps
one shared backing file until the host process exits. Closing a DB still releases
its own workers, connections and writable memory. The shared image contains
engine initialization bytes, not your schema or data. Its size is fixed per
compiled engine (about 8.5 MiB of static pages in the measured Mac prototype),
not per DB; this is not a fixed RSS guarantee. Go shares it within the Go process;
Python shares it within each managed Go host, not across independent starts or
pytest workers. Initialization failure stops new image admissions for that host;
restart the host/process after correcting the underlying error. See the
[ownership decision](decisions/process-static-image-cache.md).
