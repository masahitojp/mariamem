# Go prepared fixture — minimal API and ownership proposal

2026-10-28. Design against stable main source_commit
`cc00ccd98e29a1f5d5088a082be90a3cdaa4f469`; current branch changes are planning
documents/test tooling only. No helper implementation or build is authorized by
this proposal. [Scope](v06x-dogfood-scope-draft.md),
[milestone](v06x-go-fixture-first-milestone.md) and
[acceptance manifest](v06x-fixture-acceptance.json) are cross-checks.

## Proposed supplied entry

Separate package mariamemtest; the root runtime API is unchanged. This signature
is a review candidate, not existing API:

```go
type Options struct {
    DatabaseOptions mariamem.Options
    Prepare func(context.Context, *sql.DB, string) error
    MaxForks int                     // zero -> 2; negative rejects
    OperationTimeout time.Duration   // zero -> 120s; cooperative
}

func New(context.Context, Options) (*Fixture, error)
func Run(*testing.M, Options, func(*Fixture)) int
func (*Fixture) DB(testing.TB) *sql.DB
func (*Fixture) Close() error
```

No bare DSN/Fork ownership API, process-wide routing, automatic environment
rewrite or adaptive memory cap is part of this first helper. Existing root APIs
remain available for explicit ownership. DB uses the already-pinned MySQL driver
with default prepared execution rather than requiring SQL interpolation.
Prepare receives a helper-owned pool and DSN for migrations. A user command can
be invoked inside this callback with its context/target; normal exit0 must return
nil and nonzero exit must return the original exit error. Do not discard stderr,
secret-leak the DSN or add an implicit retry. A generic command specification API
can be designed separately; it is not needed to use ordinary command callbacks.

Callback nil means explicitly empty preparation; nil return means the declared
preparation succeeded, not that the helper inferred business correctness. Active
transactions/connections must finish before capture; no implicit Rollback=true
or constraint/engine rewrite. Close the helper preparation pool, then wait for
disconnect; user-owned DSN connections must be retired by the callback. A leaked
connection produces a bounded cooperative prepare/capture failure, not a false
baseline. A noncooperative callback cannot be forcibly reclaimed by abandoning
its goroutine; that limit stays explicit.

## Owners, capture results and admission

Acquire source → preparation pool → Prepare → pool.Close → WaitDisconnected →
Snapshot with Rollback=false. Retain owners before every error check. On success
Snapshot consumes the source; only the new baseline remains a live owner.

| Capture result | Before helper cleanup | Required helper action / oracle |
| --- | --- | --- |
| Precondition rejection / consumed=false | Source remains usable by root contract | No fixture/test admission. Dispose source once because the helper owns it; retain original rejection plus disposal failure. Test confirms source alive before this cleanup and one backend Close. |
| Accepted failure / consumed=true | Source is already closed/consumed; root capture owns partial backing unwind | No query or recapture. Attempt public idempotent source.Close to inspect stored cleanup result; it must not repeat backend shutdown. Root backing release and helper owner release each occur exactly once. |
| Success / consumed=true | Source ended, baseline owned | Register baseline. Source Close may be idempotent but must not repeat backend disposal; children use only baseline. |
| Fatal/unusable before accepted capture | Closed() may report true because the source is invalid, while disposal is still owed | Do not equate Closed with physical cleanup. Attempt public Close on the owned source and observe backend/temp cleanup. |

Always finalize an acquired source owner through public idempotent Close; never
skip it merely because HostError.Closed/source.Closed is true. Closed also covers
invalidation, not only completed disposal. Do not infer consumption from an error
string or error presence, or use that inference to double-dispose the backend.
Root TestSnapshotFailures covers flag/error propagation; helper fault injection
must prove distinct capture-consumption, stored-result and physical cleanup
actions. Internal backing returned alongside capture failure is unwound by root
Snapshot; the helper must not reach into or release it a second time.

Each distinct test owner gets a fresh child and pool. Repeated DB(t) for the same
fixture/test returns that owner's same pool instead of accidentally allocating
another DB; document this choice and test it. A subtest gets its own child only
when called with its own testing.TB. Register cleanup before publishing handles;
partially created pools/children cannot escape on Ping/acquisition failure.

Reserve a MaxForks permit **before** child startup; count starting, ready and
not-yet-reclaimed children. Release only after confirmed disposal; never release
a permit just because Close was attempted. Unconfirmed cleanup fails/closes
fixture admission rather than starting more guests beyond the budget. Wait for
permits using a caller/test context with OperationTimeout, so exhausted capacity
cannot wait forever. Parent tests must not hold a child while waiting for nested
children under an exhausted budget; return an actionable acquire failure rather
than resetting/reusing the parent's DB.

Pool max-open2/max-idle1; preparation max-open1. These are helper defaults, not a
change to root16 slots or enforcement over arbitrary externally opened pools.
Record caller overrides/external connections, and never claim a helper-owned
connection budget covers them. MaxForks is per fixture. go test -parallel limits
test scheduling, not DBs across fixtures/packages; the acceptance run pins -p1
and -parallel1/4 with cap1/2 to prove actual admission limits.

Per-test cleanup closes pool then child and reports both errors through testing
output while preserving existing test failure. Use cleanup lifetime independent
of the test's canceled Context. Fixture Close stops admission and actively
finalizes registered owned child/pool cleanup before baseline.Close; it must not
wait for future t.Cleanup callbacks that cannot run until the caller returns.
Registered and explicit cleanup share exactly-once owner finalization; later
t.Cleanup callbacks cannot double-dispose it. Explicit fixture Close ends all
helper-owned handles, unlike root Snapshot.Close which leaves started children
usable. Close returns joined errors on failure; noncooperative closure retains
the existing bounded/cooperative limits and may leave reported cleanup debt.
Run prints setup/fixture cleanup errors, does not call m.Run after failed setup,
preserves nonzero m.Run exit, and changes an otherwise-zero exit to1 on cleanup
failure. Avoid goroutine panic/Goexit tricks or global interception of assertions.

## Diagnostic decision before implementation

Proposed selected profile: readable-owned, using ordinary wrapping/Join and
testing output. Explain helper-owned stage, original cause, no-admission and
cleanup status; use a supported generic next action or explicitly unknown
reason. Tests using the ordinary *sql.DB/assertions retain normal driver/test
output. There is no attempt to reconstruct all assertion causes from m.Run's
integer exit status, which would require different instrumentation.

The user-authorized basic-first fallback is **not selected** in this proposal.
Before implementation, the approved design commit must record the profile and
feasibility rationale. If readable-owned cannot be met without global test/SQL
interception or a diagnostic framework, stop before coding the helper and record
the concrete obstacle, missing fields and chosen first-milestone exit. A later
profile downgrade requires a new decision before changing implementation.
The implementation receipt must pin the design commit and prove it is an
ancestor; no same-commit/post-hoc selection counts as pre-implementation choice.

## Acceptance and next gate

Bind named helper tests to every Go milestone obligation, especially preserved
and consumed capture failures, exactly-once cleanup and backing release, cap
waiting/cancellation, repeated DB(t), pool/child failure and Run exit behavior.
Component fakes observe owner actions; actual guest cases prove rows/schema,
committed DDL isolation and healthy later tests. Negative controls remove one
cleanup, double-dispose the consumed source, leak a permit, bypass cap or swallow
an original/cleanup error; each must be detected. A single unit PASS is not an
actual-guest or memory/FD proof. Apply the separate timing/resource acceptance,
retained-baseline input and host/source identity matrix before claiming G1 done.

Review needed now: named target scope plus this API/ownership/defaults and the
E2E hook contract. After approval, implement G1 and its focused oracles first;
P1/D1/EP1/EG1 remain separately tracked obligations. New runtime/guest work,
external-project execution, main adoption and release are not authorized by
this design proposal.
