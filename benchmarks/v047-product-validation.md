# v0.4.7 product validation — paired translator comparison

This campaign detects unexpected execution and resource regressions after moving
from the forked converter to upstream plus nine patches. It does not aim to prove
a speed improvement. Final interpretation follows the completed paired results.

## Fixed conditions

Released v0.4.6 source `b56be17206b6beef18f55c8ea39b254638da8590` versus candidate
runtime at `935c46354a2d3ab5143c39539c1f0f0566bbddc1` (subsequent runtime source unchanged). Benchmark observer
binary source `2e3182598f8d2d2e3ab3b649f2c839c80660972b`; candidate orchestrator
source and binary SHA-256 values are in the inputs. Same Apple M1, 16 GiB, macOS
27.0.1 arm64; Go1.26.8, switching disabled, identical build flags and default
runtime concurrency. No competing builds/tests/benchmarks. Python3.14 uses the
same adapter/dependencies for both states. Historical Go1.27.1 measurements are
preserved separately and are not pooled with this Go1.26.8 comparison.

The exact v0.4.6 MariaDB Wasm, generated guest function bodies, mmap ownership,
MemFS, OwnedPrepared and Snapshot/Fork implementations are unchanged. Only the
small generic base-helper delta described in the migration review is present.
Prepared views still map their owned files `PROT_READ|PROT_WRITE, MAP_PRIVATE`
(`internal/generatedgo/code/base/owned_prepared.go`, `prepared_files.go`).
This is OS page-level CoW, not cloning live MariaDB state or Unix fork.
Linear memory instead uses a new anonymous private mapping per DB. RSS includes
Go heap, stacks, code, anonymous pages and file-backed pages; these counters are
not disjoint quantities that can be added or subtracted to infer mmap residency.

Existing scenarios: Light; 10 MiB / 8 tables / serial; 10 MiB / 8 tables /
four parallel; 100 MiB / 8 tables / serial. Four tests per suite; three normal
trials and one 100 MiB trial. Fresh pays setup per DB; Fork pays prepare/Snapshot
once. Existing separate Go native fixture remains 1,000 rows ×32 bytes, one table.
Warm-up pilots precede measurement. Paired order alternates by trial/mode.

Native Testcontainers/shared-schema-reset anchors use the same immutable image
as v0.4.6 (native12.3.3 versus embedded13.1.0; 128/16 MiB buffer pools). They run
once per original cell because no translator is involved. Different versions,
durability, storage and isolation models prevent causal engine-speed rankings.
Shared schema reset does not provide independent server-global state.

## Resource interpretation

OS process Peak RSS is recorded for Go. Go heap objects are sampled at 25 ms;
TotalAlloc delta is cumulative allocation. Neither includes an estimate formed
by summing virtual reservations. Linear memory owner counters record creations,
releases and active mappings; the 2 GiB reservation is **not physical RAM**.
`peak_total_rw_bytes` is protection-enabled virtual range, not resident memory.

Phase RSS/physical footprint and Go heap are recorded separately. Final Go points
follow the harness's pre-existing diagnostic GC. Close does not promise immediate
Go arena return to the OS; RSS/physical residual is not equivalent to live heap.
FD +1 is expected one-time network poll initialization; final goroutine +1 is the
still-active observer. Prepared mapping extent is virtual, not unique/resident
file pages. No direct OS clean-page share count or mmap-only resident attribution
is asserted. Python after-SQL host samples and Docker one-shot samples are **not
Peak RSS**; those unavailable peaks are not invented.

Go suite-product wall excludes diagnostic probes/GC. Go CPU includes observation
overhead and excludes helper-child CPU. Python wall includes its observations;
CPU is runner plus reaped hosts/helpers, excluding Docker VM/container CPU.
Both candidates use identical observers. Disk is sampled every five seconds
(24 GiB budget / 20 GiB free reserve), each cell has a 900-second limit. Native
Python containers have 768 MiB / two CPU limits. Go process Peak RSS over 8 GiB
stops the campaign after the cell; no hard in-flight memory quota is claimed.

The SQL oracles check fixture values/counts, separate connections, committed
write visibility, rollback and per-child isolation; errors abort the cell. It is
not a timing-only benchmark. See [raw records and reproduction](v047-upstream-evidence/README.md).

## Completed original matrix

118 non-pilot cells plus 12 warm-up pilots completed; all SQL/transaction oracles passed.
Normal cells have n=3, large n=1. Numbers below are descriptive, not significance tests.

| Language / case / mode | n | v0.4.6 wall p50 / p95 (s) | Candidate wall p50 / p95 (s) | Median delta | CPU median (s), base → candidate |
| --- | ---: | ---: | ---: | ---: | ---: |
| go / light / fresh | 3 | 0.422 / 0.466 | 0.508 / 1.350 | +20.4% | 0.298 → 0.321 |
| go / light / fork | 3 | 0.849 / 0.878 | 0.803 / 0.842 | -5.5% | 0.744 → 0.716 |
| go / fixture / fresh | 3 | 2.918 / 2.924 | 2.923 / 3.856 | +0.2% | 3.024 → 3.032 |
| go / fixture / fork | 3 | 1.830 / 1.863 | 1.771 / 1.820 | -3.2% | 1.967 → 1.963 |
| go / parallel / fresh | 3 | 1.096 / 1.766 | 1.861 / 1.884 | +69.9% | 4.173 → 3.538 |
| go / parallel / fork | 3 | 1.374 / 1.403 | 1.298 / 1.372 | -5.5% | 2.157 → 2.155 |
| go / large / fresh | 1 | 25.649 / 25.649 | 25.842 / 25.842 | +0.8% | 28.383 → 28.689 |
| go / large / fork | 1 | 10.145 / 10.145 | 9.958 / 9.958 | -1.8% | 12.165 → 12.016 |
| python / light / fresh | 3 | 0.505 / 0.517 | 0.507 / 0.520 | +0.4% | 0.461 → 0.465 |
| python / light / fork | 3 | 0.948 / 0.964 | 0.909 / 0.936 | -4.1% | 0.904 → 0.900 |
| python / fixture / fresh | 3 | 3.012 / 3.191 | 3.014 / 3.156 | +0.0% | 3.223 → 3.213 |
| python / fixture / fork | 3 | 1.907 / 1.911 | 1.912 / 1.943 | +0.2% | 2.103 → 2.147 |
| python / parallel / fresh | 3 | 1.822 / 1.825 | 1.039 / 1.058 | -43.0% | 3.837 → 4.373 |
| python / parallel / fork | 3 | 1.321 / 1.435 | 1.342 / 1.428 | +1.6% | 2.414 → 2.362 |
| python / large / fresh | 1 | 26.364 / 26.364 | 26.531 / 26.531 | +0.6% | 29.659 → 29.819 |
| python / large / fork | 1 | 10.502 / 10.502 | 10.192 / 10.192 | -2.9% | 12.773 → 12.481 |

## Go resource comparison

All entries are median **base → candidate**. MiB uses 2^20; allocation GiB uses 2^30.
Physical footprint is a final phase sample, not a peak.

| Case / mode | Peak RSS MiB | Sampled heap peak MiB | Cumulative alloc GiB | Final live heap MiB | Final physical footprint MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| light / fresh | 287.5 → 297.4 | 151.5 → 151.5 | 0.590 → 0.590 | 0.38 → 0.38 | 176.9 → 183.8 |
| light / fork | 553.9 → 553.5 | 454.6 → 454.5 | 0.468 → 0.468 | 0.38 → 0.38 | 435.8 → 435.4 |
| fixture / fresh | 472.2 → 464.2 | 247.6 → 247.6 | 1.156 → 1.156 | 0.44 → 0.44 | 310.9 → 317.8 |
| fixture / fork | 655.1 → 644.8 | 503.3 → 503.2 | 0.653 → 0.653 | 0.43 → 0.43 | 392.3 → 401.3 |
| parallel / fresh | 789.1 → 738.6 | 973.0 → 865.6 | 1.156 → 1.157 | 0.50 → 0.48 | 448.8 → 474.7 |
| parallel / fork | 945.4 → 946.4 | 478.1 → 478.2 | 0.653 → 0.653 | 0.50 → 0.50 | 514.3 → 507.9 |
| large / fresh | 1084.9 → 1097.0 | 675.7 → 675.6 | 5.575 → 5.575 | 0.53 → 0.55 | 865.3 → 788.7 |
| large / fork | 1208.8 → 1162.5 | 799.9 → 797.5 | 1.996 → 1.994 | 0.53 → 0.51 | 966.3 → 926.6 |

## Native anchors (one shared measurement set)

| Python case | Testcontainers fresh p50 (s) | Shared schema reset p50 (s) |
| --- | ---: | ---: |
| light | 20.267 | 6.988 |
| fixture | 23.399 | 8.091 |
| parallel | 8.275 | 6.131 |
| large | 29.780 | 13.494 |

Separate Go 1,000-row fixture, n=3 suite medians (s): v046/mariamem-fresh 0.517, v047/mariamem-fresh 0.429, v046/mariamem-prepared 0.763, v047/mariamem-prepared 0.730, anchor/testcontainers-fresh 20.978, anchor/testcontainers-schema-reset 4.862.


## Startup versus work

Go per-operation wall p50 / p95 (milliseconds). Normal ready/query entries combine
12 observations clustered within three suites; Snapshot has three observations.
Concurrent phase durations overlap and are not summed.

| Case / mode / phase | v0.4.6 | Candidate |
| --- | ---: | ---: |
| light / fresh / fresh_ready | 62.5 / 141.2 | 58.6 / 616.5 |
| light / fork / fork_ready | 54.7 / 59.1 | 54.5 / 58.4 |
| fixture / fresh / fresh_ready | 59.3 / 139.0 | 60.8 / 595.1 |
| fixture / fork / fork_ready | 58.6 / 60.1 | 59.4 / 62.9 |
| fixture / fork / snapshot | 491.8 / 504.3 | 458.9 / 507.8 |
| parallel / fresh / fresh_ready | 156.5 / 1136.5 | 645.8 / 1149.7 |
| parallel / fork / fork_ready | 106.4 / 119.2 | 103.6 / 115.2 |
| large / fork / fork_ready | 59.6 / 66.5 | 62.3 / 72.1 |
| large / fork / count_use | 279.6 / 291.5 | 277.7 / 285.6 |

## Tail investigation (separate, not pooled)

The original Go Light Fresh median is +20.4% and four-parallel Fresh +69.9%,
while Python parallel Fresh is -43.0%. These are not credible opposing translator
speed claims. Ready-stage waits near one second occur in both states. Original
candidate Light trial2 spent 1.159 s in its first ready call, while CPU remained
0.331 s and total GC pause 0.87 ms. Baseline Python parallel trial0 had a 1.155 s
ready call. The added wait is not explained by measured stop-the-world pause or
a corresponding general CPU increase; its precise guest/scheduling cause is not
established. No tail was removed from the original table.

A bounded follow-up repeats only existing Light Fresh and 10 MiB four-parallel
Fresh, four paired trials each, alternating order. Same binaries/flags/SQL
oracles/observers/guards; no optimization. All 16 extra cells passed.

| Follow-up | v0.4.6 | Candidate |
| --- | ---: | ---: |
| Light suite wall p50 / range (s) | 0.432 / 0.310–0.530 | 0.391 / 0.312–0.505 |
| Light Peak RSS p50 / maximum (MiB) | 287.5 / 327.6 | 297.6 / 329.0 |
| Parallel suite wall p50 / range (s) | 1.783 / 1.755–1.844 | 1.782 / 1.006–1.850 |
| Parallel CPU median (s) | 3.375 | 3.410 |
| Parallel Peak RSS p50 / maximum (MiB) | 813.3 / 822.5 | 814.8 / 947.5 |
| Parallel sampled heap peak median / maximum (MiB) | 1012.9 / 1057.4 | 993.8 / 1140.0 |
| Parallel cumulative allocation median (MiB) | 1184.394 | 1184.293 |

The higher candidate parallel RSS high-water recurred: original maximum947.7 MiB
versus baseline814.0 MiB, follow-up947.5 versus822.5 MiB (**+125 MiB / +15.2%**
for the follow-up maxima). Do not hide this behind similar medians. It accompanies
a fast, highly overlapping run, a larger sampled heap peak, unchanged total
allocation and zero live linear mappings after Close. Lifetime overlap/GC is a
plausible explanation, **not a demonstrated cause**. The experiment does not prove
that translator/build layout has no effect on peak/tail frequency. A resident
peak increase is different from retaining more live objects after Close.

## Assessment and limits

- **Correctness / ownership: PASS within the scenarios.** Every SQL/transaction
  oracle passed; all 56 observed Go suites (40 original +16 follow-up) finish with
  zero active linear mappings, matching creation/release counts and no release
  failures. Prepared file mapping extent returns to its baseline. FD/goroutine
  counts must be read with the observer/network initialization caveats above.
- **Cumulative allocation and retained-state regression: not observed.** Original
  paired allocation median deltas stay within0.1%; final live heap remains roughly
  0.38–0.55 MiB. Physical residual is hundreds of MiB and does not become zero;
  this is also present in v0.4.6 and is not counted as live mmap ownership.
- **Typical CPU/wall cost: no sustained general tax established.** Most paired
  scenario medians are close; fresh parallel timing is tail-sensitive and reverses
  across language/order/follow-up. Small differences and three-trial p95 values
  are **INCONCLUSIVE** as improvement/regression claims. The single large trial
  cannot establish a tail distribution.
- **Parallel high-water envelope: INCONCLUSIVE, review explicitly.** The roughly
  125 MiB candidate maximum excess is real in these observations. Its frequency
  and causality remain unresolved. Similar allocation/median/reclaim counters do
  not prove equal Peak RSS. Human Review must accept this bounded transient
  envelope or require a separately scoped investigation; it is not automatically
  waived because the source diff is small. No measurement here exhausted the
  resource/disk budget or established a retained-memory leak.
- Native anchors retain the previous product context: preparation, container
  startup and cleanup model matter. No new engine-speed superiority claim follows.

There is no new CoW mechanism, VFS optimization, guest upgrade, larger soak or
canonical ×16 campaign. Existing scenario/trial counts are preserved; the only
expansion is the named bounded follow-up prompted by observed tails. macOS
measurements do not establish Ubuntu performance. Final supported-platform
artifact acceptance remains CI work. Preserve all raw JSON/CSV and the upper
outliers for the Human release decision.
