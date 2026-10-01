# v0.4 default runtime migration

Source base: `09146a46aedfb03a1177c9a3195e1a2a9f1389d2`, branch
`v0.4/generated-go-integration`. The working-tree changes and this evidence are
committed together. No tag, publication, main change or new architecture spike.
Canonical guest: `5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb`.

## Product path

**generated-Go is the default v0.4 runtime.** Go `Start(ctx, Options{})` launches
a dedicated checksum-bound guest image owned by the DB; Python `mariamem.start()`
uses the host-only wheel and that owned host's internal guest entry. Neither
normal path discovers Wasmer, downloads/looks up a native bundle, resolves
NativeDir or verifies Wasmer provenance. No arbitrary consumer executable is
rerun. See [architecture](../docs/v04-generated-go-architecture.md).

WASM is a build intermediate. Threads/TLS/FDs/wait queues and execution state
are fresh per child. Snapshot remains cold/consuming, Fork remains isolated,
with exact guest-build, inventory, hash and corruption checks. Prepared files
use private writable views with independent MemFS nodes; no ready heap,
live-worker restore, runtime sharing or OS fork was introduced.

`NativeDir` / `MARIAMEM_NATIVE_DIR` are retained compatibility bundle overrides,
not removed or required. An explicit legacy bundle keeps existing verification
and Wasmer execution. Unknown bundle kinds fail. Go `MARIAMEM_RUNTIME=wasmer`
explicitly selects the old exact-release resolver for developer/fallback tests;
empty or `generated-go` uses the default unless an explicit bundle overrides it.
Python retains explicit legacy runtime/module inputs and bundle selection;
a host override still respects an explicitly selected environment bundle.

## Acceptance

| Gate | Default generated-Go result |
| --- | --- |
| Go public Options{}: empty PATH/cache, no NativeDir | PASS: SQL, Snapshot, two forks, write/schema isolation, independent shutdown; cache untouched |
| private exact-tag consumer, no checkout replacement | PASS: default no-download/no-cache; old downloader negative/override cases intentionally select Wasmer |
| Go race integration | PASS: SQL, sessions/capacity, lifecycle, Snapshot, reconnect, timeout/cancellation cleanup |
| Python host-only lifecycle | 3/3, including timeout teardown and repeated Close |
| MySQL-wire/auth/CLIENT_FOUND_ROWS/MaxSessions | 38/38 |
| Snapshot/Fork/corruption/rollback/isolation | 50/50 |
| installed host-only wheel SQLAlchemy | 44/44, 4 × 11, no skips |
| outside-checkout GORM Options{} | 32/32, 4 × 8, repeated AutoMigrate/schema discovery retained; no skips |
| directory FD identity, MemFS grow/truncate, prepared-file isolation, thread/TLS/futex | race PASS; original deterministic regression tests retained |
| explicit Wasmer fallback | Go race integration PASS with original verified v0.3 bundle |
| ordinary checks | Go test, scoped vet, Python, public source, generated-source/image provenance PASS |

The GORM runner now rejects skipped/missing evidence rather than treating a
zero exit code as acceptance. The translator emits dead structured-control
fallthrough; the canonical vet adapter disables only `unreachable` for generated
`code/pN` packages, including dependencies. Every other analyzer remains active;
handwritten runtime/base/shim packages keep full vet. Five deterministic tests
verify that scope and failure propagation. Direct `go vet ./...` still reports
the translator's unreachable-code diagnostics; this is documented, not hidden.

Local environment is macOS27.0 arm64 on MacBook Air M1/16 GiB. The Linux-amd64
image cross-build passes; this task does not claim fresh exact-byte Ubuntu or
macOS15 release acceptance. Supported platforms remain unchanged, Windows work
was not started. Ordinary checks use an owned-source copy excluding only the
pre-existing user-owned untracked npm files; those files are unchanged.

## Reproduction / packaging

Fixed guest → candidate → imported `internal/generatedgo` replay is byte-identical
with pinned Go1.26.8 formatting. Three native-image generations retain identical
supported platform executable/encoded-source hashes. The committed generated
source and platform images have machine-verifiable provenance and source/entry
bindings; no manual patches, local candidate binaries or runtime downloads are
needed by an ordinary consumer. Full source→WASM reproducibility remains the
previous six-build evidence in [guest reproducibility](../docs/v04-guest-reproducibility.md).

Go images are 78,034,498 bytes (darwin-arm64) and 80,265,934 bytes (linux-amd64),
compressed to ~40.75 / 43.15 MiB and encoded as Go source. The complete source set
is ~326 MiB, below Go's 500 MiB uncompressed module zip limit. It intentionally
contains encoded executables as well as reproducible generated source; it is not
an assertion that the module contains no binary payload. Every DB currently
materializes its own private executable and removes it on close/failure.
Python's default wheel manifest contains only the host, with no Wasmer/WASM/AOT
runtime asset; notices/licenses remain included. Final host SHA256 is
`9beeec744a6740d6c7b2a8e426a4462cc50d0f1bdf793ee904f69c7c0c2c69f2`.
The local wheel still uses the existing development version 0.3.0 and explicitly
records `public_release_ready=false`; no v0.4 version/tag was chosen here.

Distribution follow-up candidates: Go platform image/source payload size,
per-DB delivery/launch cost, legacy native resolver/download/cache, old packaging
metadata/AOT files, Python's compatibility scratch option and release CI's native
bundle assumptions. Legacy Wasmer support/notices are retained; no GPL-derived
or third-party obligations are assumed to disappear. Go1.26.8 is pinned for
native generation: local Go1.27.1 failed the large generated arm64 package's
LDPSW code generation. Sequential developer builds bound peak compiler memory.

## Sanity measurement

20 independent fresh guests per mode, one long-lived API caller, no warmup or
removed trials. Start: public API→wire→SELECT 1. Fork: Snapshot of ordinary
1,000-row InnoDB fixture→public child→COUNT. Child/SQL pool closes between trials.
Go and Python measured sequentially, separate from acceptance. OS file caches
are not flushed; Python reuses the installed executable, Go writes a fresh
private executable each time. p50 is the median, p95 nearest rank. This is a
small sanity check, not a replacement for the canonical candidate benchmark.

| Boundary | min ms | p50 ms | p95 ms | max ms |
| --- | ---: | ---: | ---: | ---: |
| go start | 1210.8 | 1241.7 | 2212.5 | 2243.4 |
| go fork | 1274.3 | 1300.1 | 1314.9 | 1315.9 |
| python start | 86.4 | 89.0 | 120.1 | 1113.3 |
| python fork | 182.3 | 185.6 | 191.5 | 191.5 |

| Ready resource, median | Go Start | Go Fork | Python Start | Python Fork |
| --- | ---: | ---: | ---: | ---: |
| incremental physical footprint MiB | 88.03 | 85.09 | 93.90 | 91.37 |
| guest physical footprint MiB | 87.95 | 85.06 | 88.85 | 85.89 |
| incremental RSS MiB | 109.25 | 114.33 | 126.11 | 132.14 |
| CPU-sec through ready/SQL | 0.615 | 0.695 | 0.094 | 0.202 |

Counters include caller delta plus owned guest, and Python's owned host. macOS
`proc_pid_rusage` physical footprint is used, not an RSS sharing assumption.
A small post-SQL counter call is included in resource counters, not SQL latency.
After Close, median caller footprint deltas are 0.07/0.02 MiB for Go and
0.016/0.008 MiB for Python; the child/host processes terminate. These are noise/
retention observations, not an exact zero-allocation claim.

### Important Go delivery regression

**Go default is not in the earlier generated-Go startup latency range.** Its
~1.24/1.30-second median includes ~524/522 ms of stream decode, private executable
write and full checksum verification. Trace then observes ~697/692 ms from
process spawn return to ready. The latter interval includes new-executable
startup and guest work; this task does not prove an OS/code-validation cause
or attribute it entirely to MariaDB. Image delivery also raises CPU to ~0.615 sec.
Do not subtract these costs from the headline API measurement. Default Start is
slower than the historical Wasmer 308.5 ms median despite the memory reduction.
The selected-bundle ~86 ms Start/~150 ms Fork numbers excluded this per-DB image
provisioning path; the prepared-files ~34 ms spike excluded public trust/host
costs. A bounded distribution/provisioning follow-up is required before release.
No performance architecture experiment or cache was added to hide this result.

Python's host-only Start remains ~89 ms and Fork ~186 ms, within the expected
production-like generated range, with verification and wire included. It has
one 1,113 ms startup (1/20, 5%). Go has two ~2.2-second startups (2/20, 10%),
about one second above its provisioning cluster. These were retained; no futex,
condvar, InnoDB timeout or guest source change was made. This sanity run did not
independently retrace page-cleaner causality; the previously established legal
guest-side tail remains relevant. Neither path's 20-run p95 proves tail removal.
Fork had no extra one-second cluster in these samples.

Historical Wasmer Fork→COUNT p50 was 288.7 ms and ×16 incremental RSS ~280.8 MiB/DB.
Current ready guest RSS is ~109–120 MiB and physical footprint ~85–89 MiB.
Historical ×16/ORM suite figures and full candidate benchmarks retain their
original boundaries; this task did not redo scaling or 100-test benchmarking.
No pgmem/Testcontainers or release-readiness marketing claim is made.

[Small per-trial result/provenance](v04-default-runtime-migration.json) and
`benchmarks/defaultsanity`, `benchmarks/default_runtime_sanity.py` reproduce
these measurements with the existing `benchmarks/tools/process_cost.c` helper.

## Status

**DEFAULT MIGRATION COMPLETE** — the API/runtime-selection and compatibility
gates pass. This is a functional migration verdict, not release readiness.
Go image delivery latency/CPU and source size remain explicit release blockers,
alongside distribution/release-pipeline cleanup and exact-platform acceptance.
Do not tag or publish based on this migration result.
