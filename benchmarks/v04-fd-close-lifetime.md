# Lane A: retained closed Database / linked response pipe

## Scope and source

Base: `6940bf1ac3010a020c8a67cd366d9e26c42c4974`.
Branch: `experiment/v04-fd-close-lifetime`. This lane starts independently from
that exact integration SHA; no Lane B changes or integration-branch changes.
Local environment: Apple M1, macOS 27.0.1 arm64, Go 1.26.8.
This is a resource-lifetime experiment, not a canonical memory/performance run.

## Ownership and cause

`startLinked` creates two `os.Pipe` pairs. The generated execution owns
`childIn` (request reader) and `childOut` (response writer); `guest.Process` owns
`in` (request writer) and `out` (response reader). `Process.stop` closes `in`
after submitting shutdown/export. The completion goroutine waits for guest
execution, closes the child endpoints, joins `p.read`, and publishes `p.done`.
Before this experiment it did **not** close `out`.

The shortest retained path is:

`Database.server -> host.Server.Guest -> guest.Process.out -> *os.File`.

The endpoint is the host response **reader**, not a worker FD or MySQL socket.
It is already at EOF and has no remaining protocol work after `readDone`, but
EOF does not close a descriptor. `Abort` closes both host endpoints; normal
shutdown did not. A retained Database therefore kept its reader open until
os.File collection. This is accidental resource lifetime, not intentional
ownership by the closed handle, and does not explain GiB-scale footprint.
The legacy subprocess path has a different owner: `exec.Cmd.Wait` closes its
`StdoutPipe`. That path is unchanged.

## Minimal production change

`internal/guest/linked.go`: add `_ = out.Close()` after `<-readDone` and before
publishing `p.done` (one executable line plus three ownership/order comments).

This order preserves all response reads, including the Snapshot export ack,
joins the reader before closing its endpoint, and makes normal Close observe
resource release. It applies to every linked completion, not MariaDB paths,
addresses, or specific queries. Abort's earlier close remains safely idempotent.
No API, stop protocol, worker lifecycle, log stream, timeout, query cancellation,
finalizer, FD registry, generated code, or filesystem change was made.

## Reduced regression and before/after

Permanent test: `tests/godefault/fd_lifetime_test.go`,
`TestClosedDatabaseRetainedPipeLifetime` (opt-in non-race integration tier).
It warms networking once, keeps that closed handle alive, then runs three rounds
with two simultaneously live DBs. After closing A, B still executes `SELECT 1`.
All six closed handles remain alive through `runtime.KeepAlive`; repeated Close
must succeed. The descriptor count after Close must exactly equal the warmed
boundary. A retained Snapshot source handle also checks the Export completion path.
No GC, scavenging, finalizers, sleeps, or allowance masks the failure.
The inventory uses `Readdirnames` on `/dev/fd`, so it does not stat concurrently
vanished descriptor entries; its own inventory FD is included consistently.

| Observation | Base | Candidate |
|---|---:|---:|
| Warmed FD boundary | 7 | 6 |
| Six retained closed DBs + retained closed Snapshot source | 14 | 6 |
| Incremental retained FDs | **7** | **0** |
| Public regression | FAIL | PASS |

The table is the final permanent regression tested with base code restored,
then with the candidate restored. The boundary difference is the warm closed
DB's own leaked FD on the base.
A disposable exact-endpoint diagnostic also verified `p.out.(*os.File).Stat()`:
base returned nil after joined shutdown; candidate returned `os.ErrClosed`.
The six-handle candidate regression passed three repetitions (6 -> 6 FDs each).
The extended Snapshot-source variant passed three repetitions (6 -> 6 each).
That real-guest internal diagnostic was removed so the mandatory handwritten
`internal/guest` race tier does not acquire a full-generated-guest test.

## Acceptance and semantic risk

Checks on this candidate (all PASS):

- `GOTOOLCHAIN=go1.26.8 go test -p 1 ./...` (normal Go packages).
- `GOTOOLCHAIN=go1.26.8 go test -vet=off -tags=integration ./tests/godefault -run TestClosedDatabaseRetainedPipeLifetime -count=3 -v`: three final extended-case repetitions; 6 -> 6 descriptors each. `-vet=off` on this targeted diagnostic does not disable race instrumentation; normal Go check and integration also pass without it.
- `GOTOOLCHAIN=go1.26.8 python scripts/verify.py integration` using the existing project venv: focused handwritten/runtime `-race` for generated base/runtime, guest, host, wire and snapshot; normal `tests/gointegration`; normal `tests/godefault` (including prepared fixture, two Fork children, write/schema isolation and independent shutdown); host build; Python normal idempotent Close and multi-client tests (2/2).
- `python scripts/verify_generated_runtime.py`: generated source inventory, guest identity and both platform images.
- Public-source check on an owned source copy excluding `.git` and ignored work data: 550 files. Direct worktree invocation is incompatible with the checker because its `.git` pointer is a file; the checker was not changed.
- `git diff --check`.

The exact-endpoint disposable test and final public regression were both run on
base and candidate; both fail on base and pass after the fix. The known full-guest
shared-memory race and forced query-timeout reclamation limitation are unchanged
and outside this bounded lane. No performance claim is made.

Risk is low: only an owned, drained response pipe is closed, after the reader and
all guest workers have completed. Normal Close, retained handles, repeated Close,
independent live peers and Snapshot export are the relevant acceptance boundaries.
No new failure-containment guarantee is implied.

## Decision

**FD FIX IS SMALL AND INTEGRATION-READY**.

Recommendation: integrate this independent one-line lifecycle change first if
the human selects it. It changes descriptor ownership only; it should not alter
Lane B copy allocation/timing or Snapshot format. Integration is not performed
by this experiment.
