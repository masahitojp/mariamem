# Practical mariamem / Testcontainers MariaDB baseline

## Status

Measurement harness is ready; **competitive results are pending CI**. No speed
claim, target change or architecture decision is made before those data exist.
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

Pending evidence: same-job ×1/4/8 first-SQL and group-ready p50/p95, container
startup vs fixture load, mariamem waterfall, and explicitly scoped CPU/memory.
Use those results to answer whether practical advantage survives concurrency
and whether further isolation latency reduction has value relative to ordinary
Testcontainers usage. The <250 ms p50 / <500 ms p95 target remains unchanged;
relative competitor speed alone cannot establish that its absolute cost is cheap
for large test suites. No architecture recommendation is made by this harness.
