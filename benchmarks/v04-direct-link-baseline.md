# v0.4 production direct-link baseline — acceptance blocked

**NOT COMPLETE — BLOCKERS REMAIN**. Normal Go startup now directly links the
canonical generated runtime, but the full guest race acceptance fails. Canonical
performance measurement was **not started**: the task requires correctness gates
before benchmarking. Historical subprocess/spike timings are not reused as new
production measurements.

## Source and architecture

Parent: `952f379ea98a0406b689057379c3006fda384ca0`; this follow-up's runtime source
hashes and machine-readable gates are in
[v04-direct-link-acceptance.json](v04-direct-link-acceptance.json). Acceptance ran
on the uncommitted implementation represented by those hashes. Environment:
Apple M1 / 16 GiB, macOS27.0 (26A428), arm64; Go1.26.8; installed-wheel SQLAlchemy
consumer Python3.14.7. No compiler/generated-source workaround was applied. This follow-up acceptance
is macOS arm64 only; Ubuntu acceptance was not rerun after the blocking result.

`Options{}` → existing host/wire/protocol → fresh directly linked generated module.
No executable decode/write/checksum, spawn, NativeDir, Wasmer or runtime cache.
Every instance owns its linear memory, thread pool/TLS, WASIX descriptors, MemFS,
private prepared-file views and sessions. Normal completion joins workers,
exports committed Snapshot files, closes logical descriptors and unmaps prepared
views. The transport uses pipes inside one process; public APIs remain unchanged.
Python still owns a packaged host process per DB, whose guest is now directly
linked, without a second child. Explicit Wasmer bundles remain isolated fallback.

Snapshot remains consuming/cold: drain clients, shut down MariaDB, capture files,
verify inventory/hash/build identity, and start fresh execution state in each
Fork. No live heap/TLS/waiter restoration or new sharing model was introduced.

## Acceptance

| Gate | Result |
| --- | --- |
| Ordinary `go test -p 1 ./...`, scoped vet | PASS |
| Existing default integration, without `-race` | PASS: SQL/lifecycle/auth/sessions/capacity, Snapshot/Fork |
| Empty PATH/cache, Options{}, two Fork children | PASS: fixture, write/schema isolation, independent Close |
| Three repeated pairs of independent instances | PASS: repeated Close, bounded goroutine/FD retention checks |
| Installed-wheel SQLAlchemy | **44/44**, Start/Fork/Fork/Start |
| External GORM Options{} | **32/32**, including repeated AutoMigrate/schema discovery and CLIENT_FOUND_ROWS |
| Generated base/adapter `go test -race` | PASS: directory-FD identity, MemFS growth, prepared-file isolation, thread/TLS/futex reductions |
| Explicit Wasmer integration | PASS, including `-race` (10.323 s); default-only tests are separate |
| Canonical generated inventory/checksums | PASS |
| Fresh regeneration | Identical canonical provenance and both handwritten adapters |
| Full generated guest `-race` integration | **FAIL**, repeated with a single public lifecycle and with repeated-instance test |

Ordinary checkout Python checks: 388 pass / 3 skip; one publication-source test
rejects pre-existing user-owned untracked npm metadata. That test and the public
source scan pass in a managed-source copy, without changing the user's files.
A separate full-copy test attempt lacked Git metadata and is not counted as a
passing full run. Initial relative-NativeDir and wrong installed-Python-path
invocations were corrected; the results above use explicit absolute legacy bundle
and checkout PYTHONPATH, respectively.

Legacy force-kill/orphan-PID assertions remain explicit Wasmer coverage. They do
not establish forced reclamation for an in-process DB. Normal direct-link cleanup
is tested separately; arbitrary hung execution/failure containment is deferred as
requested, and is **not** the reason benchmarking is blocked.

## New acceptance gap: generated shared-memory accesses

Single `TestPublicLifecycle`, Go1.26.8, `GORACE=halt_on_error=1`, reports:

- worker: `base.AtomicRmwCmpxchg32` → `sync/atomic.CompareAndSwapUint32`;
- main agent: generated `p7.Fn88`, `p7_pure.go:356`, ordinary unsafe `int32` load;
- both access the same address in **one** module's linear memory.

Fn88 checks an expected futex value with an ordinary load before invoking
`Wasix_32v1.Futex_wait`. The bounded shim rechecks through its atomic wait path,
but that does not retroactively synchronize the generated precheck. Other reports
also involve generated ordinary loads/stores; this is not confined to the new
ownership adapter or to cross-instance state sharing. A complete non-halting
integration captured 36 distinct top access frames, primarily generated functions
and atomic assembly frames; the raw trace is disposable work output, not source.

The isolated [diagnostic](spikes/direct-link/README.md#production-acceptance-diagnostic)
calls unchanged Fn88 and the unchanged CAS helper, **without MariaDB startup,
SQL, host, filesystem or instance adapter**. A 64 KiB module has word values 0/2;
Fn88 expects 1 and always returns mismatch before the host import. Normal test
passes; `-race` reports the same conflict. This identifies a generated-memory
synchronization/instrumentation question, not a local per-instance ownership fix.
It does **not** prove a SQL malfunction, prove a cross-instance leak, or establish
that all reports are false positives under the WASM contract.

No blanket `//go:norace`, race suppression, serialization, address patches, guest
source edits, altered futex semantics or general memory-access rewrite was made.
The known legal InnoDB ~1s condition-variable startup tail was not reopened.
A transient concurrent-build `runtime` import error did not recur when the focused
race test was run alone; it then compiled and reproduced the guest memory race.

Before claiming production acceptance, classify the generated plain/atomic access
contract against WASM/WASIX and Go's memory/race model using this reduction and
representative remaining reports. A focused futex shim pass alone is insufficient.
This requires a separate bounded correctness investigation before deciding whether
a generic generator/runtime fix is necessary. It is not the known Go1.27 compiler
regression and must not be waived on that basis.

## Canonical comparison — deferred

Runtime intended for measurement: **direct-linked generated-Go**. Planned command:
`GOTOOLCHAIN=go1.26.8 python3 benchmarks/v04_candidate.py --json <work-output> --runs 30 --scaling-runs 10`
with no native-dir, plus the unchanged `benchmarks/v04_orm.py` 3-suite workload.
The harness accepts empty native-dir and expects one owning process for direct-link;
fixtures, first-SQL/COUNT boundaries and OS resource counters remain unchanged.

| Canonical metric | Historical Wasmer p50 / p95 | Production direct-link | Classification / relative difference |
| --- | ---: | --- | --- |
| Start → first SQL | 308.5 / 335.3 ms | not measured | unavailable |
| Start → 1,000 rows | 312.2 / 342.9 ms | not measured | unavailable |
| prepared Fork → COUNT | 288.7 / 349.2 ms | not measured | unavailable |
| Snapshot | 404.6 / 473.3 ms | not measured | unavailable |
| ×16 group-ready | 1.890 / 1.982 s | not measured | unavailable |
| ×16 incremental memory/DB | 280.8 / 283.0 MiB | not measured | unavailable |
| ×16 ready total | 4501.3 / 4535.8 MiB | not measured | unavailable |
| ×16 CPU | 9.463 / 9.654 CPU-sec | not measured | unavailable |
| after Close | 11.8 / 12.3 MiB | not measured | unavailable |
| SQLAlchemy100 Start | 39.012 s p50 | not measured | unavailable |
| SQLAlchemy100 Fork | 43.142 s p50 | not measured | unavailable |

No improved/unchanged/regressed label is justified without measurements. Start,
Fork, Snapshot, memory, CPU, ORM and physical retained footprint verdicts remain
unmeasured. Functional resource checks are not physical-footprint measurements.
Future comparisons must retain every slow run, use macOS physical footprint
(RSS secondary), combined owning-process CPU from baseline to all-ready, and the
existing post-Close boundary. Go heap retention must remain visible, not hidden
through forced GC or process exit.

## Packaging and next action

`internal/builtinruntime` images (~112 MiB encoded source), provisioning and
private-executable checksum/cleanup are unused by ordinary Go. Historical image
provenance, guest CLI/spawn scaffolding and legacy resolver/cache remain removable
or fallback cleanup candidates; this task does not broadly delete them.

Go1.27.0/1.27.1 arm64 remain unsupported due to upstream go#81036. The documented
upstream-fixed tip compiled the actual direct-link consumer. This known issue is
not a blocker here and no mariamem workaround is used.

**Next: resolve/classify the full generated-memory race acceptance gap.** No next
performance investigation is selected until acceptance passes and the canonical
baseline exists. Do not optimize Snapshot/Fork or choose another execution
architecture from this partial result.
