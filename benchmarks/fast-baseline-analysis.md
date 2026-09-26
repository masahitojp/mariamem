# 0.2 FAST: current isolation cost

This analysis describes the unoptimized v0.1-style implementation. Go is the
canonical core baseline; Python measures the installed-wheel consumer path.
It selects no architecture and establishes no performance thresholds.

## Evidence and measurement conditions

| Completed run | Source commit | Measurements |
| --- | --- | --- |
| [Guest startup stages](https://github.com/masahitojp/mariamem/actions/runs/36245940406) | `6b6d96189f66068c3af0996b9ab62de3e771e09c` | Python, host and guest stages |
| [Paired baseline](https://github.com/masahitojp/mariamem/actions/runs/36247078135) | `b7cebdfe0d5e00f88dde114d4d16efb1ab9cb404` | Go and Python, stages and process observations |

Both ran on GitHub-hosted macOS 15.7.9 arm64, reporting 3 CPUs, with Wasmer
7.4.2 and MariaDB `13.1.0-MariaDB-embedded`. The paired run used Go 1.26.8,
go-sql-driver/mysql 1.9.3, Python 3.14.7 and PyMySQL 1.2.3. Checkout state was
clean. These are diagnostic builds with package version `0.1.0`, not a new
release or a benchmark of the exact published v0.1.0 archive.

Guest bytes were identical across both runs and both paired consumers:

- WASM: `b46bbc8458634c16a13fcd0c242e675d6f33f72f137e70e273744613a33af9b3`
- AOT: `c002bde55b175b3f0dd8a674e77a7c5caeee8207ab058ebb97aa568c7ad1c1ac`
- Headless runtime: `ebbedfd8c43d866440b960a7b5f773b7b6932a563b6f61d043bc0c21ed535899`

Each lifecycle case has 2 warmups and 20 measured trials. The prepared InnoDB
fixture has 1,000 rows with 32-character payloads. Start readiness means a
successful `SELECT 1`; Fork readiness means a successful fixture-count query.
Parallel wall time ends when every database has completed that query. Stage
distributions contain 20/80/160 individual startups at concurrency 1/4/8.
SQL distributions are one burst of 100 queries, or 100 per client with two
clients, rather than 20 independent trials. Percentiles use linear interpolation.
CPU/RSS sampling interval is 50 ms; the post-readiness hold is 100 ms.

Raw summaries and stage summaries were recomputed successfully; provenance
matches source and WASM/AOT identities. All 308 guest traces in each report
passed the existing timing validation. Raw files remain ignored.

## Go canonical baseline and Python comparison

Measured paired-run values, **p50 / p95 in milliseconds**:

| Case | Go | Python |
| --- | ---: | ---: |
| Start → first SQL | 1,167 / 2,229 | 1,160 / 1,996 |
| Snapshot | 775 / 933 | 755 / 991 |
| Fork ×1, group wall | 1,224 / 1,936 | 1,277 / 2,153 |
| Fork ×4, group wall | 2,035 / 2,800 | 2,861 / 5,377 |
| Fork ×8, group wall | 4,222 / 5,240 | 4,652 / 5,904 |
| Fork ×4, individual DB | 1,451 / 2,468 | 2,409 / 5,253 |
| Fork ×8, individual DB | 3,384 / 4,710 | 3,700 / 5,107 |
| Steady SELECT 1 | 0.131 / 0.166 | 0.464 / 1.016 |
| SELECT 1, two clients | 0.176 / 0.217 | 0.207 / 0.773 |

The paths differ: Go runs the host in-process; Python validates inputs and
starts a separate Go host process. They also use different SQL drivers.
Python ran first, followed by Go in the same job; order was not randomized.
Prepared snapshots have equivalent fixtures, but byte-identical snapshot data
was not established.

**Measured attribution boundaries:** Python Fork ×1 spends 99 ms median in
Python-side snapshot validation and 3.5 ms in host-process spawn. Go's work
outside the host trace is 112 ms, but its individual validation/setup components
are not separated. Python/Go client connection medians are 12.6/5.9 ms.
These identify work and different connection paths, not a language-only cost.

At ×1, guest `mysql_server_init()` medians are almost identical: Python 761 ms,
Go 762 ms. At ×4 they differ: Python 1,236 ms, Go 815 ms. Thus the total ×4
gap cannot be assigned entirely to Python validation or the extra host process.
The earlier Python-only run had ×4 wall p50/p95 of 2,347/4,306 ms, versus
2,861/5,377 ms in the paired run, despite identical guest/runtime bytes.
Between-run variation is substantial. The SQL bursts likewise do not establish
a general driver or language performance ranking.

## Fork → first SQL waterfall

Go paired run, concurrency 1; **p50 / p95 milliseconds**. Indented scope is
expressed in the labels: guest rows are nested inside spawn → guest ready.

| Observable boundary | p50 / p95 | Interpretation |
| --- | ---: | --- |
| End-to-end Fork → first SQL | 1,224 / 1,936 | Caller measurement |
| Outside host startup trace | 112 / 134 | Derived duration difference; public artifact validation/setup and trace/lifecycle overhead |
| Host metadata/snapshot validation | 138 / 229 | Combined validation work |
| Host transfer preparation | 0.09 / 0.19 | Transfer setup |
| Wasmer process spawn | 3.2 / 4.2 | `cmd.Start()` duration |
| Spawn returned → guest ready | 966 / 1,636 | Host-observed envelope |
| ↳ Guest restore copy | 156 / 225 | Snapshot files copied into guest state |
| ↳ `mysql_server_init()` | 762 / 1,446 | MariaDB/InnoDB initialization, not internally separated |
| ↳ Bootstrap connection/initial SQL | 0.25 / 0.79 | Guest bootstrap |
| ↳ Ready preparation | 0.006 / 0.016 | Bootstrap close/session-slot initialization |
| ↳ Outside recorded guest interval | 56 / 76 | Derived envelope residual |
| Host MySQL wire listener ready | 0.07 / 0.13 | Listener setup |
| Client connection | 5.9 / 9.7 | Driver connection path |
| First fixture-count SQL | 1.1 / 1.5 | First successful query |

These are distributions of durations, **not additive percentile totals**.
Residuals are calculated per instance before aggregation; host and guest clocks
have independent origins. Sub-millisecond directory/open transitions and final
host bookkeeping are omitted from the compact table.

The guest interval starts at `guest_main` and ends at `ready_prepared`.
Its residual includes both pre-main runtime/CRT/static initialization and
post-instrumentation diagnostic output, ready-signal transport and scheduling.
It does **not** directly measure Wasmer initialization or exclusively pre-main
time. There is no observed “AOT runtime initialized” boundary.

Fresh Start corroborates the dominant initialization cost: Go spawn → ready is
1,008/2,057 ms, including `mysql_server_init()` at 950/2,002 ms. There is no
restore copy on fresh Start. Its residual is 60/87 ms; bootstrap remains below
1 ms at p95.

## Concurrency scaling

Go individual-stage **p50 / p95 milliseconds**, from the paired run:

| Stage | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| Host validation | 138 / 229 | 177 / 309 | 509 / 934 |
| Guest restore copy | 156 / 225 | 153 / 283 | 360 / 682 |
| `mysql_server_init()` | 762 / 1,446 | 815 / 1,935 | 2,072 / 3,387 |
| Envelope residual | 56 / 76 | 58 / 164 | 111 / 340 |
| Outside host trace | 112 / 134 | 140 / 193 | 296 / 440 |

**Derived:** ×1 → ×8 median initialization grows by 1,311 ms, the largest
measured stage increase. Host validation grows by 371 ms and restore by 204 ms.
Median per-instance initialization shares are 60.2%, 59.4%, 59.0% at ×1/4/8;
restore shares are 12.3%, 10.9%, 10.4%. These use individual sample ratios,
not ratios of aggregate medians.

The earlier Python stage run independently shows the same hierarchy: median
initialization is 856/1,149/1,918 ms at ×1/4/8; restore is 135/319/385 ms.
The paired Python values are 761/1,236/2,004 ms and 177/392/539 ms respectively.
Exact scaling varies; initialization consistently dominates.

## CPU and memory observations

Paired-run **medians**, per parallel group; CPU seconds and MiB:

| Observation | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| Go sampled runtime CPU | 0.980 | 3.705 | 8.045 |
| Go runner CPU | 0.291 | 0.902 | 1.909 |
| Python sampled host + runtime CPU | 1.170 | 5.895 | 9.755 |
| Python parent CPU | 0.156 | 0.558 | 1.046 |
| Go sampled runtime peak RSS | 338 | 1,377 | 2,245 |
| Go sampled whole-tree peak RSS | 354 | 1,393 | 2,261 |
| Python sampled host + runtime peak RSS | 342 | 1,397 | 2,275 |
| Go incremental ready RSS per DB | 337 | 344 | 265 |
| Python incremental ready RSS per DB | 341 | 348 | 277 |

Go runtime CPU p95 is 1.673/4.873/10.331 seconds. **Derived:** median runtime
CPU per DB is approximately 0.98/0.93/1.01 seconds, while latency grows markedly.
This is consistent with contention, but does not identify its mechanism.

Sampling reported no errors. Descendant CPU can miss startup/shutdown edges;
runner/parent CPU includes harness, driver and cleanup work over a different
window. Go's host is included in runner CPU/RSS; Python's sampled descendants
include its separate host and exclude the Python parent. Do not sum these
median CPU columns as exact accounting or compare RSS as language efficiency.
RSS sums shared pages, misses peaks between samples and is not unique physical
memory. Ready RSS uses the nearest sample and baseline subtraction. Lower ×8
RSS per DB is not evidence of an isolation architecture saving memory.
There is no per-stage CPU attribution or steady-state memory measurement.

## Snapshot and materialization

| Paired snapshot boundary | Go p50 / p95 ms | Python p50 / p95 ms |
| --- | ---: | ---: |
| Total | 775 / 933 | 755 / 991 |
| Export acknowledgement | 301 / 402 | 297 / 414 |
| Host publication | 348 / 418 | 364 / 452 |
| Outside host trace, derived | 93 / 111 | 95 / 124 |

Export acknowledgement combines MariaDB shutdown and guest filesystem export.
Publication combines copying, inventory/hash verification and manifest commit.
Neither is further separated; snapshot CPU/RSS observations are unavailable.
The earlier run measured export/publication medians of 247/307 ms, again showing
both are meaningful preparation costs.

Snapshot is template preparation, not work repeated inside each Fork. Fork's
restore copy is measurable, but much smaller than full MariaDB initialization.
Copy-only improvements cannot be assumed to eliminate the isolation cost.

## Architecture-review inputs

**Measured bottlenecks:** MariaDB initialization dominates single and parallel
Fork; restore copying and host validation are the next substantial Fork stages.
Snapshot publication/export also matter when preparing templates frequently.

**Unknowns:** initialization has no internal engine/allocation/recovery breakdown;
the runtime envelope residual mixes several boundaries; validation and
publication do not split hashing from copying; no I/O volume, page-fault,
per-stage CPU or unique-memory accounting exists. These runs do not establish
Ubuntu performance, large-fixture behavior, cold-cache behavior or repeatability
across hosted machines. Earlier local latency numbers are not interchangeable
with this 3-CPU runner baseline.

**Hypotheses, not architecture choices:**

- Avoiding repeated full MariaDB initialization could affect more latency than
  reducing snapshot copy alone; feasibility and correctness remain unproven.
- Eight databases on three reported CPUs may contend during initialization and
  validation. Stable runtime CPU per DB does not prove CPU is the only constraint.
- Repeated validation may be a meaningful parallel-isolation cost, but its
  hashing/I/O breakdown and safe alternatives require separate investigation.
- Pre-main runtime initialization may contribute to the residual; attributing
  the whole residual to Wasmer is unsupported.

## Raw result identity

The downloaded JSON files are retained locally under ignored
`benchmarks/results/run-<run-id>/`. Their SHA256 values identify the evidence
used here independently of its download location:

| Run / JSON | SHA256 |
| --- | --- |
| 36245940406 / `guest-startup-stages.json` | `6d7643ea44bb16bfa42328544e06116ac1685885d6c19b8f3ae6eceec729c6b6` |
| 36247078135 / `go-startup-stages.json` | `351870c350de6a5b1ab23e3b1ba43e4f899d87fe554b5af6788cf8cfdda5cd8c` |
| 36247078135 / `guest-startup-stages.json` | `ca01be10b2a3d43b2d596b53caf145553acf2120c87a40f1f56e9b9c1579a049` |
