# Final v0.2 FAST fixed-local acceptance

**PASS — v0.2 FAST target met**

Measured on 2026-09-29, using clean main commit
`a32ac4f6129fccbab57c45a706a4340c335771f1`. This commit changes only analysis
relative to the production 2-worker verification implementation at `a48e223`.
The acceptance rule is unchanged: prepared-state startup **p95 <500 ms**.
This result closes that measurement milestone on the fixed reference below.
It is not a hardware-independent or per-platform latency guarantee.

## Reference environment and exact artifacts

| Item | Recorded identity |
|---|---|
| Machine | MacBook Air, MacBookAir10,1 |
| CPU | Apple M1, 8 cores (4 performance + 4 efficiency) |
| RAM | 16 GiB (17,179,869,184 bytes) |
| OS | macOS 27.0, build 26A428; Darwin 27.0.0 |
| Architecture | arm64 |
| Go | go1.26.8 darwin/arm64; GOARM64 v8.0 |
| Runtime | Wasmer 7.4.2 |
| Server | 13.1.0-MariaDB-embedded |
| Supervisor | Python 3.9.6; measurements execute the public Go API |
| Native package metadata | 0.2.0a1, darwin-arm64, minimum macOS 15 |

The public production native archive was downloaded from `v0.2.0-alpha.1` and
matched against its published SHA256SUMS. Its AOT, sidecar and runtime hashes
also match the macOS inputs accepted by CI run 36522659284; no rebuild, AOT
compilation or artifact modification was performed for this measurement.
The current Go host was built from the clean measured main commit, with pinned
Go 1.26.8. The guest/runtime release source and current host checkout are distinct
identities, as expected for the unchanged reusable guest build boundary.

| Artifact | SHA256 |
|---|---|
| Native archive | `2d2cb684d078ffc99fde67742d18a3c79a68f70c6c4e933b2b95ff4f628492d1` |
| mariamem.wasmu | `a74927f01e387f8d60fecb5e61a182e344b6a0d2b524d735817e5d632bcc6d4d` |
| mariamem.wasmu.json | `e32e81d0a68481837958d6451c922b92d74063363fdb13f40da46706573a9b3a` |
| wasmer-headless | `ebbedfd8c43d866440b960a7b5f773b7b6932a563b6f61d043bc0c21ed535899` |
| Measured Go runner | `4c636a4787a5458f534017a0fdbc4d240f1575622e08918b24b211c615afece5` |
| Aggregate raw JSON | `f1275cd041a221f0069280b592005093a5947a420bdfdfeae450dd148a30c902` |

The Python environment reports an older installed mariamem distribution, but
that package is not the measured implementation: the supervisor invokes the
newly built Go executable and explicit verified NativeDir. Likewise the Go
module's inferred pseudo-version uses locally available tags; `vcs.revision`
and `vcs.modified=false` identify the actual clean measured commit. Neither
incidental package label substitutes for the source/artifact identities above.

## Method and complete distribution

```sh
GOTOOLCHAIN=go1.26.8 .venv/bin/python benchmarks/final_latency.py \
  --native-dir build/fixed-reference-native/mariamem-native-darwin-arm64 \
  --production-only --runs 30 \
  --json benchmarks/results/final-v02-local.json
```

Each trial launches a fresh Go process, prepares the existing 1,000-row,
32-character fixture and Snapshot, then measures public Fork through connection
and verified first fixture query. Fixture preparation/Snapshot is outside Fork
timing. Stage/init diagnostics are OFF; the existing 50 ms ps sampler remains.
Two explicitly labelled warmups are retained in raw reports and excluded from
percentiles, as established by the existing method. All **30 measured trials**
are included; no slow measured trial or failed result was discarded.

| Metric | min | p50 | p95 | max |
|---|---:|---:|---:|---:|
| Fork → first successful SQL (ms) | 341.268 | 374.203 | 417.681 | 446.071 |
| Go runner SELF CPU (CPU-sec) | 0.151 | 0.165 | 0.187 | 0.192 |
| Sampled runtime descendant CPU (CPU-sec) | 0.240 | 0.270 | 0.321 | 0.330 |
| Process-tree sampled peak RSS (MiB) | 350.6 | 356.6 | 390.0 | 390.5 |
| Incremental sampled ready RSS (MiB) | 298.6 | 337.9 | 349.5 | 352.1 |

All child processes returned success; there were no sampler errors. All 30
latencies were below 500 ms. Linear-interpolated p95 has 82.3 ms headroom on
this sample. This describes 30 observations, not a statistical guarantee about
all future runs. No affinity/cache flushing/OS tuning was performed; normal
local machine resource state is part of this reference observation.

CPU counters cover broader batch intervals including hold/cleanup, with sampled
runtime startup/exit edges possibly missed. Do not sum independent CPU medians
as exact first-SQL CPU. Peak RSS may double-count shared pages; incremental ready
RSS subtracts the pre-Fork process-tree baseline (median 15.8 MiB) and may use a
sample before full ready state. It is not private/PSS or unique physical memory.
No new memory diagnostics were run and no memory optimization is claimed.
This acceptance is not a same-machine serial-vs-parallel CPU/memory A/B.

Raw samples, child JSON/logs and recorded runner metadata stay ignored under
`benchmarks/results/final-v02-local*`; the sanitized additional reference metadata
is `final-v02-local-reference-environment.json`. Only this analysis is committed.

## Hosted CI and production optimization

[The paired hosted regression](two-worker-verification.md) measured repeatable
27–37 ms median latency improvement across five Ubuntu jobs using identical
native bytes. Host CPU increased slightly (roughly 0.1–1.7% in the observed
broader interval); there was no consistent material sampled peak-RSS regression.
Both-platform packaged Go/Python acceptance and lifecycle/race tests passed.
The bounded 2-worker optimization therefore remains production behavior.
It preserves all required integrity checks and does not establish persistent trust.

GitHub-hosted jobs are correctness and regression monitoring, not the absolute
performance reference: unchanged-code job medians previously ranged from
354 to 544 ms with model-associated hardware regimes. No hosted job is discarded
for missing 500 ms. This local PASS does not assert fixed-local Ubuntu p95 <500 ms;
Ubuntu product correctness is supported by the separate CI acceptance.

## v0.2 closure checklist

No additional runtime/product optimization is required by this fixed-reference
acceptance. The first FAST tranche, bounded verification change, both-platform
packaged lifecycle correctness, ×16 isolation/cleanup and 16-session envelope
have evidence. Memory remains a documented cost; CPU/memory numeric budgets
remain provisional rather than new release blockers. Larger restore/runtime
architecture work and ORM dogfood are not required to close this measurement.

The final v0.2 release itself still requires the explicit human version/release
decision, release-facing notes/status/version preparation and the existing exact
candidate multi-platform Release CI guard/publication transaction. This benchmark
neither substitutes for those checks nor publishes or declares that candidate
READY. The durable project-status KPI text predates the final stricter p95 rule;
release-status preparation should reconcile it with this reference result without
turning performance numbers into public hardware-independent guarantees.
