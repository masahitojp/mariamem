# Practical mariamem / Testcontainers MariaDB baseline

## Status

**Completed:** [run 36359174307](https://github.com/masahitojp/mariamem/actions/runs/36359174307)
passed on source `a8e5d5b1d828e639933885ae4b70531b33e76129`. Both workloads
show a same-run latency advantage at ×1/4/8; this does not establish a universal
performance ranking, memory advantage, or final FAST architecture.
The comparison starts from main's v0.2.0-alpha.1 implementation (`8b44e9d`), not
from either restore experiment. Product behavior and restore are unchanged.

## Exact workload and environment

Dispatch `guest-build-boundary.yml` with only `competitive_baseline=true`.
It builds/verifies canonical guest WASM once (or reuses exact verified inputs),
then runs AOT and both competitors on the **same Ubuntu 24.04 x86_64 job**.
Go is 1.26.8; Python is 3.14; Wasmer is 7.4.2 with SSE2+SSSE3 AOT baseline.
The pinned official MariaDB image is 11.8.9 Linux/amd64:

`docker.io/library/mariadb:11.8.9@sha256:de4cf325ed1fc8a22460b4f285de7b9e06d89edbd593505e678ec480f86e501b`

The image digest was resolved from the official registry's platform manifest.
The Docker inspect identity is verified after pre-pull; pull/build time is
separately recorded and excluded. Testcontainers Go MariaDB module is v0.40.0
in a separate benchmark-only module with pinned transitive dependencies; the
product Go module/dependencies are unchanged. Each trial uses `mariadb.Run`,
no reuse option, a fresh data volume, the module's normal ready-log wait and an
explicit SQL connection. No custom server configuration or tmpfs shortcut is
introduced. The reaper is initialized during excluded warmups.
Actual `SELECT VERSION()` results, Docker/server environment and native/AOT
metadata are retained. Embedded MariaDB is currently 13.1.0, unlike container
11.8.9; version equality is not claimed. The default auth, memory/cache and
persistence policies also differ; this is practical usage, not identical engines.
[Official image](https://hub.docker.com/_/mariadb/) and
[Testcontainers API](https://golang.testcontainers.org/modules/mariadb/) document
these inputs; the checked-in lock and actual result evidence control this run.

## Timed boundaries

Both paths use the same Go SQL driver and the established fixture SQL:
`benchmark_rows(id INT PRIMARY KEY, payload VARCHAR(64)) ENGINE=InnoDB`,
1,000 rows with 32 `x` characters, one bulk insert in a committed transaction.
Both verify count and payload length; fixture setup SQL is not tuned per backend.

- **Empty:** public `Start` or fresh `mariadb.Run` → explicit connection →
  correct `SELECT 1`. Module ready wait, container creation and entrypoint/server
  initialization are inside Testcontainers timing. Pulls are outside.
- **Fixture-ready:** mariamem prepared Snapshot → public Fork → connect →
  correct fixture COUNT. Testcontainers fresh container → server/connection
  ready → CREATE/INSERT/COMMIT → correct COUNT. Container startup/connect and
  fixture load are reported separately, along with the actual total.
- Snapshot preparation (Start, fixture load, disconnect, Snapshot) is recorded
  separately. Its amortization depends on how many independent DBs use it;
  it is not represented as free single-use setup.
- Each batch starts ×1/4/8 DBs together and retains all until all return correct
  SQL. Individual latency starts within each admitted worker; group readiness
  starts at batch dispatch and ends at the last successful first SQL.
- Each scenario/concurrency has two warmup rounds and 20 measured rounds, each
  executing both backends in alternating order. Raw samples preserve round and
  position. Cleanup completes before the next condition; cleanup is outside
  readiness latency. Warm caches remain; caches are not flushed.

## Accounting and waterfall

After all DBs are ready, collect version and costs, then shut down. Diagnostic
collection cannot delay another DB's first SQL. This is near-ready memory,
not peak RSS or a perfectly simultaneous sample.

- mariamem: cumulative Wasmer process CPU from `/proc/<pid>/stat`, CLK_TCK
  recorded by `getconf`, and resident pages × page size. Excludes the in-process
  Go host; RSS includes shared mappings and is not unique physical memory.
- Testcontainers: Docker one-shot cgroup CPU since container creation and
  memory usage/raw memory stats. Includes entrypoint/init and server processes;
  memory includes cgroup-charged cache. This is **not equivalent to RSS**.
- Go runner cumulative batch CPU is separate. It includes mariamem's in-process
  host or Testcontainers orchestration, excludes Docker daemon and the reaper.
  DB/cgroup counters may include small work after readiness. Unavailable
  accounting is an explicit error/missing metric, never estimated or zero-filled.
- mariamem caller, host and guest startup events use existing monotonic timing.
  They retain preparation/validation, restore, embedded initialization,
  readiness, connect/first SQL and unobserved residual. Nested stages overlap;
  stage medians are not additive and residual is not automatically Wasmer time.

## Outputs and local reproduction

On Ubuntu with Docker, from a clean checkout and verified native directory:

```sh
python3 scripts/verify.py bench competitive --native-dir build/guest-aot --runs 20 --warmup 2
```

JSON/raw observations and summary Markdown are ignored under
`benchmarks/results/testcontainers-comparison.*`. CI uploads them with manifest,
AOT provenance and image lock as `competitive-ubuntu24.04-<source SHA>`.
Incomplete runs retain partial observations and the failing boundary, and fail
CI rather than publishing an apparent result. No performance threshold is used.

## Verified run and artifact identity

Measured environment: Ubuntu **24.04.5 LTS**, x86_64, Linux 6.17.0-1022-azure,
glibc 2.39, 4 visible CPUs; hosted image `20260920.314.1`. Docker 28.0.4 used
`overlay2` and reported 15.62 GiB host RAM. Go was 1.26.8. Server versions were
**13.1.0-MariaDB-embedded** and **11.8.9-MariaDB-ubu2404** in every observation.
The pinned image resolved to image ID
`sha256:cc7f5fdd7c8fff6867e8ac4df3e7e0faf6c56aebe621a13565479a9a94e4bf13`;
platform and RepoDigest match the checked-in lock.

The common WASM was verified and **reused**, with original guest source commit
`d44157adbc527da6482e205c176616489cb3ccbc`. Ubuntu AOT was **rebuilt** on the
measurement checkout and verified/sealed. The AOT provenance `source_commit`
refers to that original guest producer, not a different measured Go host.
This is the supported measurement-input reuse model, not new release evidence.

| Identity | SHA256 |
|---|---|
| Measurement JSON | `8208b8b2c6ca13f0bf785fc80d8a6bf49e3eafc30434f73ce3161a8a001fe102` |
| Common WASM, CI verified | `41e3acfb51fe52ad13d9691de0bd3f05619266571e84dd1a0ddf263e082add7f` |
| Ubuntu AOT, CI verified | `e729fc07d7cb03de6b4bbf5334f0e1da460a8abfff56b0d3661b2688969e73fb` |
| Native manifest | `e9d7a89169d84a2c0e8f6009b27fa931c8af2f3d2b38016480dd4d09b034b108` |

Downloaded raw evidence stays ignored at
`benchmarks/results/competitive-36359174307/competitive-ubuntu24.04-a8e5d5b1d828e639933885ae4b70531b33e76129/`.
Metadata/provenance copies, manifest digest, image identity and all summary/stage
percentiles were checked against raw data. All **264 batches / 1,144 DBs**
(including warmups) completed. Measurement contains 20 paired rounds per
scenario/concurrency, 20/80/160 individual DB observations per backend. Group
readiness reconciles with the latest per-worker ready time. Alternating order,
round completeness and timing subdivisions reconcile. CI's successful runner
also enforced the fixture query, payload lengths and cleanup for every instance.
Parallel DB samples within one batch are correlated; there are 20 independent
rounds, not 160 independent hosted environments.

### First SQL and group readiness

All values **milliseconds, p50 / p95**. Empty = Start; fixture = Fork or fresh
container plus fixture creation. The factor is **container p50 / mariamem p50**,
a derived ratio of pooled medians, not a per-trial speedup distribution.

| Scenario | DBs | mariamem first SQL | Testcontainers first SQL | mariamem group ready | Testcontainers group ready | p50 factor |
|---|---:|---|---|---|---|---:|
| empty | 1 | 255.2 / 274.0 | 4748.9 / 8293.8 | 255.2 / 274.1 | 4748.9 / 8293.8 | 18.6× |
| empty | 4 | 444.6 / 508.6 | 7985.8 / 10490.1 | 488.3 / 519.0 | 9444.1 / 12758.2 | 18.0× |
| empty | 8 | 821.4 / 913.3 | 13675.1 / 17876.8 | 895.5 / 931.7 | 16341.6 / 18798.8 | 16.6× |
| fixture | 1 | 527.5 / 534.9 | 5580.7 / 7040.2 | 527.5 / 534.9 | 5580.7 / 7040.2 | 10.6× |
| fixture | 4 | 692.8 / 775.6 | 7459.2 / 10136.6 | 734.1 / 786.5 | 9375.4 / 10897.5 | 10.8× |
| fixture | 8 | 1221.4 / 1312.9 | 14670.8 / 17879.7 | 1295.5 / 1342.9 | 16803.8 / 19370.8 | 12.0× |

**Measured fact:** mariamem was earlier in all 20 paired batch-mean comparisons
for each of the six scenario/concurrency combinations. Paired median
container-minus-mariamem batch-mean differences were empty **4.50 / 7.75 / 12.49 s**
and fixture **5.04 / 6.95 / 13.25 s** at ×1/4/8. This checks that the advantage
is not merely an artifact of subtracting pooled medians.

Parallel isolation retains the practical latency advantage. It is not free:
fixture individual p50 grows 527 → 693 → 1,221 ms and group-ready p50 grows
527 → 734 → 1,295 ms. Container fixture individual p50 grows
5,581 → 7,459 → 14,671 ms; group-ready grows 5,581 → 9,375 → 16,804 ms.

### Testcontainers startup versus fixture setup

| DBs | Startup + module wait + connect p50/p95 ms | Fixture CREATE/INSERT/COMMIT p50/p95 ms | Actual total to COUNT p50/p95 ms |
|---:|---|---|---|
| 1 | 5573.1 / 7032.4 | 7.2 / 9.4 | 5580.7 / 7040.2 |
| 4 | 7450.4 / 10128.9 | 9.1 / 14.1 | 7459.2 / 10136.6 |
| 8 | 14658.8 / 17872.2 | 11.4 / 32.7 | 14670.8 / 17879.7 |

**Derived from each sample:** fixture setup is only 0.135% / 0.117% / 0.084%
median of the total at ×1/4/8; its p95 share stays below 0.24%. The difference
is overwhelmingly the fresh-container/server-readiness workflow, not loading
1,000 rows. This does **not** isolate Docker overhead from MariaDB initialization,
entrypoint data-directory creation, log waiting or connection setup.
The latter remain one large bucket without container-internal stage timings.
Empty and fixture conditions were measured in separate scenario blocks; their
startup medians differ despite tiny fixture load. Treat that as startup/run
variation, not evidence that the fixture adds hundreds of milliseconds.

One mariamem snapshot preparation took **906.5 ms**, separately recorded.
Image pre-pull/inspect/info took **6.03 s**, excluded. Warmups excluded reaper
first use. A single fixture DB therefore has extra snapshot preparation to
amortize; the main fixture latency table assumes the prepared state already
exists, as intended. This is not a container snapshot comparison.

### CPU and near-ready memory observations

CPU is seconds **p50 / p95 per DB**, runner CPU is **per whole batch**.
Memory is MiB p50/p95 with explicitly different scopes.

| Scenario | DBs | Wasmer process CPU | Container cgroup CPU | Go runner CPU: mariamem / TC p50 | Wasmer RSS | Container cgroup memory usage |
|---|---:|---|---|---|---|---|
| empty | 1 | 0.190 / 0.230 | 3.714 / 7.722 | 0.068 / 0.101 | 408.238 / 415.824 | 134.145 / 135.865 |
| empty | 4 | 0.310 / 0.330 | 6.224 / 8.794 | 0.286 / 0.619 | 409.129 / 415.100 | 133.867 / 135.661 |
| empty | 8 | 0.310 / 0.330 | 6.260 / 9.874 | 0.569 / 1.621 | 406.314 / 414.855 | 133.959 / 136.010 |
| fixture | 1 | 0.330 / 0.351 | 4.818 / 5.829 | 0.173 / 0.117 | 404.207 / 413.534 | 135.207 / 137.470 |
| fixture | 4 | 0.360 / 0.400 | 5.719 / 8.741 | 0.728 / 0.525 | 399.350 / 419.258 | 135.398 / 137.574 |
| fixture | 8 | 0.370 / 0.400 | 6.653 / 9.338 | 1.469 / 1.698 | 398.682 / 415.055 | 135.354 / 137.226 |

All ready-cost samples were available. **Measured fact:** the container's broader
startup cgroup CPU counter is much larger than Wasmer process CPU in this run.
The comparison does not quantify pure engine efficiency or total host CPU:
Docker daemon/reaper are excluded, and Go host work is separate. Runner CPU
is not always smaller for mariamem (fixture ×4: 0.728 vs 0.525 s per batch).
Counters are gathered after group readiness and can include peer waiting,
version-query work and near-ready background activity; Wasmer CPU has clock-tick
resolution. They are not CPU strictly bounded at each worker's first SQL.

**Measured fact:** mariamem still has roughly 399–409 MiB observed RSS per ready
instance; container cgroup usage is roughly 134–135 MiB. No memory advantage is
established. RSS/shared mappings and cgroup usage/file cache are different
accounting scopes; peak startup memory and unique incremental physical memory
were not measured. Smaller measured container memory does not prove a precise
physical-memory ratio, nor does lower latency establish cheap memory isolation.

Configuration was constant within each backend. Both report Aria page cache
and MyISAM key buffer 128 MiB, `innodb_flush_log_at_trx_commit=1`, `sync_binlog=0`.
The InnoDB buffer pool is **16 MiB mariamem / 128 MiB container**, and
`skip_grant_tables` is **ON / OFF**. Container account/grant initialization and
full root password authentication are real default work; mariamem's public
connection semantics remain different. Nothing was changed to equalize or win
these defaults. Version, filesystem, durability path and auth differences limit
causal interpretation of the competitor gap.

### Current mariamem Fork waterfall

Milliseconds **p50 / p95**, based on the same fixture condition. Rows are actual
stage durations except the explicitly derived enclosing residuals. Nested rows
must not be added and neither may stage medians be added into a synthetic total.

| Observable interval | ×1 | ×4 | ×8 |
|---|---|---|---|
| End-to-end first SQL | 527.5 / 534.9 | 692.8 / 775.6 | 1221.4 / 1312.9 |
| Caller work outside host startup trace, derived | 65.0 / 65.3 | 69.6 / 79.0 | 135.2 / 181.6 |
| Host metadata/snapshot validation | 104.5 / 105.6 | 111.9 / 121.1 | 227.2 / 293.1 |
| Wasmer process spawn | 0.34 / 0.36 | 1.29 / 3.66 | 2.25 / 9.55 |
| Spawn-returned → guest-ready envelope | 348.1 / 356.6 | 480.1 / 585.4 | 821.7 / 920.9 |
| ↳ Guest snapshot restore | 232.8 / 239.4 | 282.2 / 407.3 | 471.0 / 629.7 |
| ↳ Embedded MariaDB server initialization | 79.6 / 92.8 | 132.7 / 166.6 | 217.0 / 287.8 |
| ↳ Envelope outside recorded guest interval, derived | 35.5 / 37.2 | 57.3 / 67.1 | 110.1 / 165.2 |
| Database returned → client connected (includes Ping) | 6.37 / 10.89 | 10.82 / 25.69 | 18.66 / 51.80 |
| Connected → first SQL | 1.02 / 1.27 | 1.37 / 3.07 | 1.59 / 5.25 |

The outside-host duration is computed per observation from caller
`database_returned` minus host trace duration. It includes public preparation
and return work; those are not split further here. The spawn/guest residual is
not pure Wasmer time. Restore accounts for **44.1% / 42.1% / 39.3%** median of
each sample's total at ×1/4/8. It remains the largest individual measured Fork
stage and grows most in absolute p50 time (233 → 471 ms); engine init,
validation and residuals also grow. No read-only or direct-WASI experiment is
active. Empty Start ×1 is 255.2 ms, including 141.4 ms median embedded init and
no restore; empty initialization differs from opening the prepared state.

### FAST target: value and remaining gap

**Measured fact:** this practical comparison already demonstrates a substantial
latency advantage without hitting <250 ms Fork p50. Competitor parity therefore
does not require that target. It remains useful as an absolute test-suite cost
objective: prepared Fork still costs about 0.53 s individually and 1.30 s to
ready eight DBs on this four-CPU runner, alongside hundreds of MiB observed RSS.
A faster competitor-relative number does not settle CPU/memory cheapness.

**Derived bound, not an optimization result:** subtracting each observation's
entire measured restore duration from its end-to-end time gives ×1
p50/p95 **294.7 / 307.8 ms** (×4 393.1 / 424.1; ×8 727.3 / 809.6).
Even the fictional zero-restore case stays above 250 ms p50 here, assuming all
other measured costs remain fixed. Real changes can affect contention and
other stages, so this is a bounded thought experiment, not a hard architectural
lower bound. The actual ×1 p95 is 534.9 ms, also above 500 ms.

**Trade-off / unknown:** pursuing the target may improve repeated suite latency
and resource headroom, but the measured competitor advantage alone does not
justify maintaining a custom filesystem/runtime. This run cannot choose a new
boundary or establish whether the remaining target is worth a specific cost.
The target is unchanged; no production architecture is selected.

## Historical context — not paired competitive measurements

| Historical case | Environment | First SQL p50 / p95 ms |
|---|---|---:|
| v0.1-style Go Start | macOS, baseline `b7cebdfe` | 1167 / 2229 |
| v0.1-style Go Fork ×1 | macOS, same run | 1224 / 1936 |
| v0.1-style Go Fork ×4, individual | macOS, same run | 1451 / 2468 |
| v0.1-style Go Fork ×8, individual | macOS, same run | 3384 / 4710 |
| First FAST tranche Fork ×1 | Ubuntu, `d44157a` | 539.2 / 566.4 |
| First FAST tranche Fork ×4, individual | Ubuntu, same run | 734.8 / 807.1 |
| First FAST tranche Fork ×8, individual | Ubuntu, same run | 1289.1 / 1404.6 |

See [original baseline](fast-baseline-analysis.md) and
[production tranche](fast-tranche-baseline.md) for identities and limitations.
These are different runs/hardware/instrumentation, not controlled differences.
Production ×1 restore was about 231 ms on Ubuntu and 196 ms on macOS; prepared
RSA keys and within-call validation reuse are integrated. No direct-WASI or
other experimental restore behavior is used here.

## Inputs for the next FAST architecture review

- **Measured:** current mariamem empty first-SQL p50 is 255/445/821 ms versus
  4.75/7.99/13.68 s for the normal container workflow. Fixture-ready is
  527/693/1221 ms versus 5.58/7.46/14.67 s. Advantage survives ×8 and all
  same-round batch-mean comparisons; this is one hosted run and two MariaDB versions.
- **Measured / derived:** fixture load is 7–11 ms median and below 0.24% of
  container total even at the p95 share. Startup is the competitor bottleneck;
  its internal CPU/wait/filesystem causes are unobserved.
- **Measured:** mariamem's own largest Fork stage is restore (233 → 471 ms),
  followed by mandatory validation/preparation and engine/residual work.
  Process spawn itself remains small. Parallel cost exists despite the advantage.
- **Measured with scope limits:** Wasmer process CPU is lower than container
  startup cgroup CPU; Go host CPU is material and separate. RSS remains roughly
  400 MiB per mariamem instance; no memory advantage or unique-physical footprint
  has been established.
- **Decision input, not a target change:** <250 ms is substantially beyond what
  is needed to show advantage against this default Testcontainers workflow, but
  remains an absolute cheap-isolation objective. Fictional complete restore
  removal alone leaves ×1 p50 near 295 ms in the same samples. Use absolute
  suite cost, memory and maintenance burden as well as competitor latency in
  the architecture discussion. No next architecture is recommended here.
