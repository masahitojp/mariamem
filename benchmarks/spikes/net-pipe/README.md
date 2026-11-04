# Issue66: same-process net.Pipe transport spike

2026-11-05, Apple M1 / macOS27.2 arm64, Go1.26.10, GOMAXPROCS8,
go-sql-driver/mysql1.9.3. **Recommendation: continue toward a small opt-in Go
connection API.** The fixed local comparison shows lower elapsed time for all
four workloads, with the same MySQL handshake/protocol/guest path. Adoption and
main integration require a separate Human decision.

The strongest objection is additional per-operation allocation and an extra
connection path to maintain. This is a microbenchmark of one host and one
client; it does not establish application/suite speedup or a memory reduction.
No Linux/race/public API/Snapshot lifecycle acceptance has been completed.

## Hypothesis and bounded implementation

`go-sql-driver/mysql -> net.Pipe -> internal/mysqlwire -> existing guest`
can avoid loopback TCP overhead without a new SQL driver or guest patch.
[Config.DialFunc](https://github.com/go-sql-driver/mysql/blob/v1.9.3/dsn.go)
uses the driver's existing per-connector extension point; no global dialer
registration or driver fork is needed.

Experiment-only `internal/host.Server.DialPipe` creates a pair and hands the
server end to the same `attach` admission path used by TCP accept. The lock,
slot reservation, activity/transaction state, query monitoring, failure abort,
close acknowledgement and worker join remain shared. Rejected handshakes are
also tracked: an unread pipe rejection must be closed/joined during shutdown.

[net.Pipe is synchronous and unbuffered](https://pkg.go.dev/net#Pipe); packet
encoding, goroutine scheduling, copies and read-deadline coordination still
occur. It is not a direct embedded-SQL API. TCP listener startup, Python/CLI,
public Database/fixture APIs, default transport and guest/generated source are
unchanged. Dialing checks an already-cancelled context; later handshake/query
cancellation belongs to the driver/connection deadlines as with TCP.

## Correctness

Final source runs17 spike leaf cases plus6 existing host leaf checks, all PASS:

- Both TCP/Pipe: handshake/SELECT1; explicit prepared parameter execution;
  transaction commit/rollback;16-session limit with SQL1040 and slot reuse;
  Close with idle clients and an unread handshake, followed by query rejection.
- Both TCP/Pipe: driver query deadline while SLEEP runs invalidates the instance;
  subsequent connections fail. The contract still waits for worker completion,
  rather than promising immediate reclamation of non-cooperative guest work.
- Pipe: cancelled Dial does not admit a session; expired read deadline;
  unread capacity rejection is tracked and joined by Close; injected guest
  Abort rejects a new handshake with SQL2013; concurrent Dial/Close terminates.

Zero active registered clients after cleanup and successful worker join were
checked. This is not a whole-process goroutine/RSS leak campaign. The failure
case injects host Abort, not an independently reproduced guest panic/I/O fault.
The earlier source also passed its then-current suite; correctness.json separates
that run from final additional cases. No oracle was weakened after a failure.

## Fixed comparison

Five fresh processes alternate TCP-first / Pipe-first. Each process exercises
both modes with the same executable, guest, SQL and driver settings. Each of
40 final cells uses1,000 serial operations. The one-iteration workload probe
checks result shape and is excluded from the performance summary.

| Workload | TCP median | Pipe median | Elapsed reduction |
| --- | ---: | ---: | ---: |
| Connect + handshake + Ping + client close |507.43us|224.71us|55.7%|
| Warm SELECT1 |127.95us|83.66us|34.6%|
| Warm explicit prepared SELECT ? + 1 |175.47us|88.23us|49.7%|
|64 rows x128-byte payload |1513.80us|1031.26us|31.9%|

Medians are across the five process-level ns/op observations per mode;
reductions are computed from those medians. All raw observations and paired
speed ratios are retained. They are averages within each process/cell, not
per-query latency percentiles or confidence intervals.

Warm SQL uses maxOpen1/maxIdle1. Connection measurement uses maxOpen16/maxIdle0,
so each Ping establishes and returns/closes a new driver connection; it includes
client-side cleanup, not a separately timed server-close acknowledgement.
The result query is `SELECT REPEAT('x',128) FROM seq_1_to_64`, scanned fully;
setup verifies64 correct payloads. Prepared parameters use the real statement
path, not interpolation. Build, DB startup, Fork, fixture setup and final teardown
are outside the operation timer. GOMAXPROCS is fixed8, and no concurrent load is
added. This is a TCP-vs-Pipe comparison of the experiment, not a before/after
benchmark of the unmodified main accept implementation.

| Workload | TCP B/op | Pipe B/op | TCP allocs/op | Pipe allocs/op |
| --- | ---: | ---: | ---: | ---: |
| Connect/Ping |19513|21204|227|237|
| SELECT1 |9104|10845|98|123|
| Prepared1 |9514|11267|107|132|
| Result64x128 |98512|116414|804|1081|

These are Go benchmark allocation medians. They are not retained heap/RSS,
CPU usage, FD savings or overall resource-cost measurements. Result transfer
has about18% more allocated bytes and34% more allocations here.

## Identity and reproduction

Baseline source_commit `c27061f1a33eed2908fd90b0e2d816692e001339`.
Measured source_commit `4d0b3efac0d59341099c1ef6b4f6bfc863172b75`.
Initial source_commit `5e2ce8f5f637afb4a3a30fd7d32d1561657eb6f4`.
Metadata records the final executable SHA256, guest/input hashes and clean source
identity checked with scripts/git_identity.py before build. Go's test executable
has no VCS build fields; no VCS-stamped host claim is made. Final build used a
clean standalone shared clone; the evidence commit is later than measured source.

Use an experiment workspace with3GiB owned budget and6GiB free reserve.
Check out measured source into `TASK_WORK/temp/source`, then:

```sh
python scripts/git_identity.py --root TASK_WORK/temp/source inspect HEAD
GOTOOLCHAIN=go1.26.10 GOCACHE=TASK_WORK/temp/go-cache \
  GOTMPDIR=TASK_WORK/temp/go-tmp GOMEMLIMIT=3GiB GOGC=50 \
  go -C TASK_WORK/temp/source test -vet=off -p 1 -tags issue66 -c \
  -o TASK_WORK/temp/host.test ./internal/host
# From this evidence source, with an absolute TASK_WORK path:
python scripts/experiment_disk.py --work-dir TASK_WORK \
  --min-free-gib 6 --budget-gib 3 --timeout 900 -- \
  python benchmarks/spikes/net-pipe/run.py TASK_WORK
```

The collector stops on correctness or fixed-workload probe failure. It does not
patch SQL or retry failed tests. Executable test source is gated by `issue66`;
no heavy permanent CI job is introduced.

## Next decision

Continue only if a Go-specific opt-in API and the allocation tradeoff are useful.
For a product candidate, define Database/fixture wiring and closed/failed lifecycle
semantics, then obtain Linux/focused race and relevant Snapshot/Fork ownership
coverage. Exercise deterministic concurrent Dial/Close admission before adopting;
the current scheduler race test is a spike, not exhaustive concurrency evidence.
Do not merge this exploratory history as-is. Guest/upstream patches: none.
Listener-free startup, other languages, performance under concurrency and changes
to SQL/wire feature coverage remain out of scope.

The45-minute active-work budget permits this finite spike; it is not an elapsed
build-time result. Source/report/evidence refs are pushed, and task-owned clones,
compiler cache, binaries and completed worktree are removed after collection.
