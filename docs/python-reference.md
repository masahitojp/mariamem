# Python options and lifecycle reference

For your first test and prepared fixtures, start with the [Python guide](python.md).

## Published wheel platforms

Python 0.6.2 wheels support macOS 15+ arm64, Linux x86_64/aarch64 with
glibc 2.28+ or musl 1.2+, and Windows build 22000+ x86_64/arm64.
Python 3.11+ is the package minimum, not an exhaustive tested-version matrix.
See [installation](../README.md#installation) for pip commands and the distinction
from Go tag support. A CPU, OS/libc minimum or manifest mismatch raises an
artifact/platform error before host use; install the matching wheel rather than
copying a host from another platform. Published wheel OS adapters come from the
0.6.2 maintenance source; current main source is a separate development product.

## Snapshot ownership and host lifetime

`snapshot()` fixes a baseline with private immutable blocks in Go memory.
Ownership and immutability are enforced without rescanning every byte during
ordinary heap capture. Internal imports, transfers and copies from borrowed
file mappings retain their content checks.
It ends the source DB and retains the baseline in the automatically managed host.
Fork creates a
fresh MariaDB runtime and private changes; it does not copy running threads.
One independent `start()` owns one host lineage. Its baseline, children and
derived baselines share that host. Each DB has its own SQL endpoint and a limit
of 16 simultaneous connections. The Snapshot itself uses no SQL connection.
The host exits when the last owned handle and admitted operation finish.

Version 0.6.1 adds a finite per-Snapshot Fork budget:

```python
import mariamem
import pymysql


with mariamem.start() as setup_db:
    setup_db.wait_disconnected()
    with setup_db.snapshot(max_forks=2) as baseline:
        assert baseline.max_forks == 2  # Read-only, resolved at capture.
        with baseline.fork(timeout=30) as child:
            with pymysql.connect(**child.connection_info()) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    assert cur.fetchone() == (1,)
```

Omitted `max_forks` resolves once using one quarter of detected memory at
256 MiB per slot, with a finite CPU fallback. This is a sizing heuristic, not
an OOM guarantee or a CPU/latency optimum; use an explicit positive integer
when tuning concurrency. The Go host validates Linux sysinfo units and proc
MemTotal independently, retaining the smaller valid observation; readable
cgroup/Go limits still apply when physical readings fail. CPU fallback is only
for no valid memory observations. Values must be built-in integers in 1..2147483647;
zero, bools and larger values reject before capture. Each worker and each
Snapshot owns a separate budget; their totals are not a machine-wide limit.
Close each child before synchronously requesting another when capacity is full.

If the container memory limit is unreadable or invisible, auto sizing can use
host RAM and admit more children than the container can afford (for example,
64 GiB host RAM can resolve to64 despite a hidden512 MiB container limit).
Set an explicit cap in that environment. Independent root `Start` / `start()`
calls are outside Snapshot caps; finite Fork defaults are not a global DB limit.

`baseline.fork(timeout=30)` bounds capacity waiting in positive finite seconds
(at most 2147483647). The equivalent constructor is
`Database(snapshot=baseline, fork_timeout=30)`. Omission waits while a responsive
host reports full capacity; submission, reservation responses and startup still
have finite watchdogs. A capacity timeout reports `pool_timeout` / `fork_wait`
without closing existing children. Its message reports the resolved `max_forks`,
`occupied_slots` from the last responsive full reply and the action "close owned
children or increase max_forks". If expiry precedes any capacity reply, occupancy
is explicitly `unknown`. These are observations, not a new reservation or a claim
that the count is unchanged when the error is read. Parent Close wakes capacity waiters and
preserves admitted children. Separate development-host handoff holds the origin
slot until actual target disposal. Unconfirmed cleanup stops new admission;
retry the responsible owner's cleanup. Normal late disposal alone does not
automatically reopen admission. Supplied pytest/E2E/Django entries now forward
their settings. Finite admission shipped in 0.6.1. See the
[adoption decision](decisions/issue53-fork-limit-adoption.md) for accepted limits
and [current release evidence](project-status.md#current-published-release) for
exact-version qualification; older receipts retain their own SHAs.

If capture fails and closing the newly owned Snapshot also fails, the shared
host permanently retains `captureDebt`. That owned-Snapshot Close error is
cached and cannot be retried; the originating slot stays occupied and its
parent's admission stays stopped even if runtime disposal later completes.
Cleanup retry or Live Reset cannot recover this pool. Safely close remaining
owners and prepare a fresh independent lineage. This is a stricter limitation
than retryable child-runtime cleanup debt, not a claim of eventual slot release.

SQL errors and an individual DB's normal Close do not close siblings. A host
process crash invalidates that lineage's DBs and baselines; prepare again.
Independent `start()` calls use independent hosts. Non-cooperative guest cleanup
can retain resources until the lineage ends; an individual request timeout does
not authorize killing a host with other live owners.

Snapshots are process-local. Saving/loading baselines, path-based acquisition,
path-taking capture such as `db.snapshot(path)`, `snapshot_to`, `load_snapshot`
and `Snapshot.open(path)` are unavailable in this version.
Re-run migrations/seed to prepare a baseline in each test session.
Old persisted artifacts are not inputs to this API. The library does not manage
an automatic cache. Internal handoff for an explicitly different development
host binary is temporary and is not a public save operation.

Creation checks inventory, layout, seal state and guest/source identity while
retaining the same backing. Ordinary heap acquisition does not perform a full
content reread. Fork reuses the fixed blocks and copies changes privately;
it does not fully hash content on every Fork. Internal import/transfer boundaries
and borrowed-mapping copies retain their content validation.

## Connections, timeouts and failures

Current session capacity is 16; this is not a permanent API limit or throughput
guarantee. Connections have separate transactions, temporary tables and session
variables. Extra connections receive recoverable MySQL error 1040. Disconnect
cleanup must finish before a slot is reusable.

`startup_timeout`, `query_timeout` and `shutdown_timeout` use positive finite
seconds and default to 120, 30 and 30. Snapshot `timeout` defaults to 120 seconds;
shutdown has a deadline, but freeze/content validation has no size-independent
interruptible deadline. `wait_disconnected(timeout=...)` bounds session waiting.

SQL/driver exceptions and unsupported commands are listed in
[compatibility](compatibility.md).

Ordinary SQL errors do not invalidate the DB. Query timeout or disconnect during
active SQL does: `closed` becomes true and `status()` raises
`HostError(code="unusable", closed=True)`. Close it and start/fork another.
Idle disconnect does not invalidate it. A fatal guest
worker trap also invalidates the DB promptly and reports its cause without waiting
for the query timeout. Forced cleanup of non-cooperative execution is not guaranteed. Prepared boundaries are described above.

`HostError.code` identifies startup/lifecycle categories; `stage` supplies
diagnostic context and `__cause__` retains a Python cause. Startup failure
returns no usable DB. `logs` retains a bounded diagnostic tail after cleanup.
Explicit `log_path=` files are preserved; default logs are cleaned up.
For a platform/artifact mismatch, reinstall the matching wheel rather than
combining files from releases. `start(host_binary=...)` is a development override.

Current internal architecture and technical limits belong in
[architecture](v04-generated-go-architecture.md); published historical
measurements are [evidence](../benchmarks/v043-characterization.md), not a
performance promise.


## Local OpenSSL4 and Connector/Python

Homebrew Python3.14 with OpenSSL4 can fail to import Oracle
mysql-connector-python 26.7.0 because `ssl.PROTOCOL_TLSv1` is absent. The observed
combination is Python3.14.9/OpenSSL4.0.3. CPython conditionally omits protocol
constants for methods unavailable in OpenSSL4; this connector accesses those
constants during import. This happens before connecting to mariamem. It is
separate from the native-matched prepared-result limitations above.

Record the Python/OpenSSL versions and original import error when reporting a
local integration failure. Use the CI-supported Python/OpenSSL profile for the
fixed consumer checks; retain FAIL for the affected local run. Do not add ssl
aliases, patch the connector or change drivers to label that run PASS. The
current OpenSSL3 CI environment does not cover this OpenSSL4 combination. See
[local verification](development.md#local-verification).


## Pytest fixture options

| Fixture | Scope | Responsibility |
|---|---|---|
| `mariamem_options` | session | Start options; default `{}` |
| `mariamem_server` | session | Preparation DB; consumed by successful Snapshot |
| `mariamem_prepare` | session | None, preparation callback or `PrepareCommand` |
| `mariamem_max_forks` | session | Since 0.6.1: finite Snapshot cap; default `None` selects auto |
| `mariamem_fork_timeout` | session | Since 0.6.1: per-child capacity wait; default30 seconds, positive finite only |
| `mariamem_snapshot` | session | Fixed baseline captured after preparation |
| `mariamem_fork` | function | Independent mutable DB for one test |
| `mariamem_connection_info` | function | Driver arguments for that test's DB |

For prepared tests, return your migrations/seed callback from
`mariamem_prepare` in `conftest.py`. The installed plugin calls it once per
worker, closes its source after use and owns the disconnect wait, Snapshot and
per-test Fork teardown. Use the platform wheel from [installation](../README.md#installation).

Since 0.6.1, override `mariamem_max_forks` with a positive
integer and `mariamem_fork_timeout` with positive finite seconds when needed:

```python
# conftest.py: optional settings alongside your mariamem_prepare fixture.
import pytest


@pytest.fixture(scope="session")
def mariamem_max_forks():
    return 2

@pytest.fixture(scope="session")
def mariamem_fork_timeout():
    return 30
```

These settings validate before the preparation callback/command. The supplied
child fixture always uses a finite wait; `None` is rejected. A held child can
exhaust the cap: acquisition then fails at its deadline, preserves the original
diagnostic and stops dependent test admission in that worker. Close the held
child; increasing the wait does not fix a child that never closes. Each xdist
worker owns a separate Snapshot budget; tune worker count and cap independently.

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
