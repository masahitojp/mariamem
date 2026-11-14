# MemoryEA product verification (2026-11-15)

The minimal direct-panic plus explicit `//go:noinline` candidate retains a
promising whole-suite improvement without distribution growth. Proceed to the
existing exact-source platform/consumer CI qualification. This is a local
verification result, not adoption, READY, main integration or release approval.

The strongest limitation is variability: P1 and P8 suite elapsed improved in
only 3/5 pairs. The observed improvement must not be advertised as a guaranteed
percentage or as closing the gap with another engine. No additional samples
were selected or discarded to improve the conclusion.

## Source and change

- Baseline main source_commit: `9d1ea060b3180bbba8424f30383b47fa6859ebb3`.
- Measured product source_commit: `e7644172e2356588fc77e8ebdbbf9656120860cd`.
- Product Go 1.26.10, macOS arm64. Sources resolved with `scripts/git_identity.py`.
- Canonical wasm2go `pure-memory32.patch`: express failure with direct panic,
  explicitly prohibit MemoryEA inlining, remove its unused trap helper.
- Full canonical translation and installation changed only generated
  `code/base/base.go`, image layout and provenance. Bounds arithmetic, memory
  size loads, guest Wasm, SQL, APIs and engine function files are unchanged.
- Translation/input and license evidence bindings updated; no new attribution
  tolerance or inventory exemption. No historical experiment logs are merged.

The direct panic communicates a non-returning failure path to Go; explicit
noinline retains the normal-path simplification without copying bounds/panic
code into callers. Prior isolated disassembly established 23 to 20 normal-path
instructions. This run measures the product candidate; it does not reattribute
all wall-time savings to those three instructions.

## Current-main comparison

[All 36 process observations and phase aggregates](results.json) retain warmups,
source identities and actual distribution hashes. Each measured arm has five
processes per parallelism; one preceding warmup is excluded from statistics.
Each process executes 70 test bodies, 20 writer Forks and 21 sample insertions.
All 36 processes passed (2,520 bodies, 720 writer Forks, 756 samples).

| Parallelism | Baseline suite median ms | Candidate suite median ms | Paired suite change median | Paired process-wall change median | Paired CPU change median |
|---|---:|---:|---:|---:|---:|
| P1 | 1565.379 | 1543.205 | -2.65% | -2.63% | -2.03% |
| P4 | 775.737 | 700.197 | -11.49% | -6.99% | -9.62% |
| P8 | 685.655 | 623.584 | -10.11% | -9.33% | -6.19% |

Absolute columns are independent process medians; percentage columns are
medians of `(candidate / baseline - 1)` within the same numbered pair.
They therefore need not agree arithmetically. Suite elapsed improved in 3/5
pairs at each P; process wall in 3/5, 5/5, 3/5; CPU in 4/5, 3/5, 4/5.
P8 process-wall changes range from -25.20% to +8.05%. Shared host, only five
pairs and an active capacity monitor limit precision. These observations do
not supersede the previous differently pinned experiment's measurements.

Phase p50 below is the median of each process's phase p50, in milliseconds.
Parallel phases overlap; do not add these columns to reconstruct elapsed time.

| Parallelism | Writer Fork baseline → candidate | Sample baseline → candidate | Test body baseline → candidate |
|---|---:|---:|---:|
| P1 | 17.774 → 17.319 | 46.740 → 44.273 | 1.310 → 1.196 |
| P4 | 28.137 → 27.172 | 77.497 → 67.288 | 1.826 → 1.732 |
| P8 | 40.297 → 39.093 | 126.914 → 123.980 | 2.562 → 2.661 |

P8 test-body p50 increased; this is not an across-the-board phase speedup.
Process-wall timing includes startup/exit and cold-process costs, but this is
not a separately controlled cold filesystem-cache experiment.

## Actual distribution sizes

Official `scripts/build_alpha.py --ci-candidate`, clean source clones, same
unchanged 0.6.2 version, no publishing. Both wheel archive checks passed.

| Artifact | Baseline bytes | Candidate bytes | Difference |
|---|---:|---:|---:|
| mariamem-host (retained symbols) | 104146194 | 104146098 | -96 |
| macOS arm64 wheel | 49419836 | 49419906 | +70 |

Distribution size is effectively unchanged. These are actual host/wheel bytes,
not estimates from a test executable. Hashes are in results.json.

## Correctness, provenance and verification limits

- Canonical regeneration/fixture verification passed. Independent big.Int
  boundary oracle covers 24,641 cases, plus bound growth and concurrent atomic
  size updates. Existing generated-memory CRUD/Fork/trap checks passed.
- `scripts/verify.py check --profile daily` passed at the second product commit
  `02e5cbdef9b3e852efa69874885ebee96f6fdff4`: source oracles 88 tests,
  broad Python 2,061 passed / 99 intentional skips / 119 subtests, Go unit/vet,
  generated inventory and public-source checks.
- Canonical integration passed its race packages, Go integration/generatedmemory,
  live smoke, Python 53 passed / 1 skip and Snapshot 33 checks. The whole command
  did **not** exit successfully: prepared Connector/Python consumer import hit
  the known OpenSSL 4 `ssl.PROTOCOL_TLSv1` incompatibility. The Human explicitly
  excludes this external issue from this task's blockers; no workaround or
  investigation is included. CI still owns its consumer results.
- Found and repaired an existing verification selector: it named the nonexistent
  `TestWorkerTrapActualGuest`, missing the real
  `TestWorkerTrapActualGuestNotifiesAndIsolatesPeer`. The final selector runs it
  and `TestDictionaryWaitActualGuest`; both actually passed locally. Two Python
  contract tests now check the real declarations (11 focused tests passed).
  This selector-only change forms e7644172; runtime bytes did not change after
  the canonical check. Later report-only commits are not claimed as new runs.
- Fresh license audit rechecked the unchanged guest/map and all generated engine
  files, and all 18,035 retained host function symbols across 12 component
  families. The source-bound audit host is 434712e8. Prior linked-artifact identity
  is explicitly inherited from the accepted audit/build manifest: linked bytes
  and the sysroot were **not** freshly reopened. See the maintained
  `release/generated-license-evidence.json` method/prior_link_audit records.
- A license reconstruction test assumed a metadata transition always existed.
  It now constructs that transition explicitly in its fixture, keeping negative
  tampering checks. Focused translation/license/inventory tests: 70 passed.
- Go's local VCS discovery stamped an enclosing repository when using a nested
  worktree. That build was rejected. Final builds use clean independent shared
  clones with real .git directories; their stamps match their fixed commits.

## Reproduction and remaining qualification

The exact Close-corrected harness is Git object
`523a8883d434af381f7a9d00a2c6ae571eefc172:benchmarks/memory-ea-inline/suite-20261115/harness.tar.gz`,
SHA256 `e10c2ba5ab3bd7a0185506904a4f3649c7e4be1dc0002946e774d23176b6de1c`.
Extract the Maria harness, use Go 1.26.10 and replace its product module path
with each fixed clean source clone. Build both suite executables before timing:
`go test -c -p 1 -vet=off -o <arm>.test ./store`, CGO_ENABLED=0.
Run with GOMAXPROCS=8, GOGC=100, MODELCASE_MATCHED=1, MARIA_AUDIT_OF=1,
REVENUE_PREAGG=1, original SUM/all triggers and no profiling/experiment flags.
Select `^Test(GetOrder|ListOrders|SearchProducts|TopProducts|RevenueByCategory|CreateOrder|ApplyDiscount|DeleteUser|ShipOrder|CancelOrder)$`
with `-test.parallel=1`, then 4, then 8; timeout 150s. For each P run one warmup
per arm, then five pairs alternating baseline-first/candidate-first. Collect
MODELCASE_TRACE, process wall, child user+system CPU and `/usr/bin/time -l` RSS.
The compact observations retain every process and phase aggregate, enough to
recompute the reported statistics without preserving full successful logs.

Remaining: submit the final exact candidate to the existing Release candidate
READY workflow with `operation=verify`, `mode=auto`. CI owns supported-platform
and consumer qualification. No new version, main merge, publication or CI
supervision is part of this submission. A CI success is still separate from
Human adoption of the candidate.
