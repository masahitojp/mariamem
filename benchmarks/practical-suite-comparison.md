# Fixed-reference repeated isolated-test comparison

## Method

This benchmark compares practical workflows, not equivalent engine internals or
an unconditional winner. Primary venue is the same Apple M1 MacBook Air / 16 GiB
macOS 27.0 reference used by final v0.2 FAST acceptance. Docker Desktop is already
running; image download and Go compilation are outside timed suites. Record its
VM CPU/RAM allocation and existing background container count, not merely host RAM.
No DB cache settings, durability or auth configuration is changed for either side.

Use the existing synthetic migration (one CREATE TABLE) and 1,000-row / 32-character
InnoDB fixture; this is not a complex application migration or ORM integration.
Each isolated test verifies count/payload and mutates a row. The next test must
observe the pristine row, so reset failures fail the measurement, not disappear.
The Testcontainers MariaDB module uses its normal startup/readiness/connection
path with no container reuse. Migration SQL and test SQL match both backends.

| Condition | Isolation boundary | Preparation |
|---|---|---|
| mariamem-fresh | Fresh guest/runtime/server and schema per test | Start + migration/fixture every time |
| mariamem-prepared | Fresh guest/runtime/server per test from cold Snapshot | Start + migration/fixture + Snapshot once per suite, included in total |
| testcontainers-fresh | Fresh MariaDB server/container/data volume/schema per test | Run + migration/fixture every time |
| testcontainers-schema-reset | One server/container per suite; fresh schema and client pool per test | Run once, then DROP/CREATE schema + migration/fixture per test |

Schema reset does not reset global variables, plugin state, engine caches, users,
server settings or unrelated schemas. It is not equivalent to a fresh server.
Transaction rollback is another weaker boundary: it does not generally undo
DDL/nontransactional or global/session effects; it is discussed, not mixed into
these results. Reusing a container across suites further changes lifetime and
state guarantees; it is not enabled here.

The main measurement uses 10/50/100 sequential isolated tests, three independent
suite trials per condition/count, rotating condition order. One separate 1-test
warmup per condition is labelled and excluded. All measured suites/tests are
retained. Three suite repetitions expose one-off noise but their interpolated
p95 is descriptive, not a strong tail estimate. Per-test samples are correlated
within a suite. Suite totals include actual preparation, allocation, test SQL and
cleanup, plus explicitly recorded resource-observer/checkpoint bookkeeping.
They do not multiply an isolated-startup median to fabricate a suite duration.

Memory is observed at first/last ready state (every fresh-container ready state),
with OS high-water marks and cgroup v2 memory.peak where available. Runtime RSS,
Go host RSS and container cgroup usage/peak are distinct scopes; container values
exclude the shared Docker VM/daemon. Resource observation cost is recorded and
must be considered especially for fast schema resets. CPU includes runner SELF,
waited local child CPU and container cgroup CPU where observable; teardown edges
and auxiliary processes prevent an exact apples-to-apples total.

The official image 13.1.0 lookup failed, whereas the embedded server identifies
itself as 13.1.0. The arm64 official 11.8.9 platform manifest is pinned in
`practical-suite-inputs.json`. It runs natively inside Docker's Linux arm64 VM;
no amd64 emulation, special init scripts, reduced caches or tmpfs shortcut.
This version/default-configuration difference must remain explicit.

## Run

```sh
GOTOOLCHAIN=go1.26.8 .venv/bin/python benchmarks/practical_suites.py \
  --native-dir build/fixed-reference-native/mariamem-native-darwin-arm64 \
  --runs 3 --counts 10 50 100 \
  --json benchmarks/results/practical-suites.json
```

The script validates all native hashes and native arm64 image identity before
execution. Raw suite reports/logs and aggregate JSON remain ignored in
`benchmarks/results/`. A failed SQL/correctness/cleanup step fails the run;
missing suite/test evidence cannot silently contribute to a passing summary.
Owned DB-container IDs are checked absent after completed suites. It does not
stop unrelated containers or alter mariamem product behavior.

## Reference identity

Measured code is clean main commit
`9a5b12dd97d3c491f46c0fbee2df1129e87d44a1`; production behavior is unchanged
from the final v0.2 reference. This uses the public Go API and the verified
published native bundle, not a fake engine or a rebuilt experimental guest.

| Item | Value |
|---|---|
| Date | 2026-09-29 |
| Host | MacBookAir10,1 / Apple M1 / 16 GiB / macOS 27.0 build 26A428 / arm64 |
| Go / Testcontainers | Go 1.26.8; Testcontainers Go MariaDB module v0.40.0 |
| Runtime / native package | Wasmer 7.4.2 / 0.2.0a1 |
| mariamem server | 13.1.0-MariaDB-embedded |
| Container server | 11.8.9-MariaDB-ubu2404 |
| Docker | Desktop 4.92.0 (240144); Engine 29.8.0; LinuxKit 7.0.12 |
| Docker VM | Linux arm64; 8 CPU; 8,319,770,624 bytes allocated; overlay2 |
| Other containers | 3 already running at measurement start; not stopped or modified |
| Native archive SHA256 | `2d2cb684d078ffc99fde67742d18a3c79a68f70c6c4e933b2b95ff4f628492d1` |
| AOT SHA256 | `a74927f01e387f8d60fecb5e61a182e344b6a0d2b524d735817e5d632bcc6d4d` |
| Image arm64 platform digest | `sha256:d61191467af1bb3e1bf29077c3af7bb41574da6aba245e79540a970ea2cfa767` |

The native runtime and sidecar were also hash-verified; the full native manifest,
Go build metadata, runner SHA256 and Docker versions are retained in raw JSON.
No production cache/durability settings are changed. Observed defaults differ:
mariamem's InnoDB pool is 16 MiB versus the image's 128 MiB; both report 128 MiB
Aria and MyISAM cache settings, `innodb_flush_log_at_trx_commit=1` and
`sync_binlog=0`. mariamem keeps its default `skip_grant_tables=ON`; the image uses
normal configured authentication. Version/configuration and native-macOS versus
Linux-VM execution are real product differences, not controlled engine A/Bs.

## Results

The first full attempt completed all 10- and 50-test suites, plus both mariamem
100-test suites in round 0. Its first 100-test fresh-container suite stopped
after 66 completed tests: the Testcontainers `ConnectionString` call returned
`port "3306/tcp" not found`. This means container inspection did not expose a
usable host port at that point; it does **not** establish a MariaDB SQL failure,
physical-disk problem, or a proven Docker/Testcontainers root cause. The harness
attempted container termination and aborted instead of retrying invisibly. The
failed startup did not retain its container ID or termination outcome, so cleanup
of that particular failed container is not independently proven by its report.

The failed run, successful prefix and logs remain intact. A separate 100-test
repeat used the same code, native/image bytes, defaults and three-round method;
no wait strategy, configuration or engine behavior was changed to rescue it.
Its checkout dirty flag reflects only benchmark documentation drafts; the runner source
remains `9a5b12d`. The difference is retained in provenance, not concealed.
That repeat failed with the same error after **71** completed tests. The two
successful prefixes lasted 328.670 and 361.532 seconds, excluding the failing
startup. There is **no completed 100-test fresh-container suite**, so neither
its total latency nor its suite p50/p95 can be inferred. This is an observed
benchmark failure, not evidence that Testcontainers generally has this failure.
No reaper/readiness setting or MariaDB configuration was changed to make it pass.

The existing runner's `--suite-mode` was then used to complete the remaining
conditions, without another full retry: one additional 100-test suite for each
mariamem mode and three for schema reset. Including the successful suites from
both earlier attempts gives three complete repetitions for those conditions.
This recovery loses full order balance and temporal pairing; report it as a
practical descriptive comparison, not a randomized paired experiment.
Suite distributions distinguish completed suites from the failed attempts.
The fixture is deliberately small; do not generalize to expensive migrations or
production-scale workloads.

| Tests | Condition | Suite wall p50 / p95 (s) | Fixture-ready p50 / p95 (ms) |
|---:|---|---:|---:|
| 10 | mariamem fresh | 3.638 / 3.679 | 322.9 / 363.9 |
| 10 | mariamem prepared | 4.386 / 4.453 | 308.6 / 325.9 |
| 10 | Testcontainers fresh | 51.304 / 61.188 | 4817.0 / 7537.3 |
| 10 | Testcontainers schema reset | 3.822 / 7.821 | 12.3 / 15.5 |
| 50 | mariamem fresh | 17.331 / 17.915 | 317.9 / 344.7 |
| 50 | mariamem prepared | 17.414 / 18.486 | 295.7 / 324.8 |
| 50 | Testcontainers fresh | 245.473 / 264.798 | 4566.0 / 7222.8 |
| 50 | Testcontainers schema reset | 5.185 / 5.733 | 11.1 / 14.1 |
| 100 | mariamem fresh | 34.450 / 35.573 | 315.4 / 343.1 |
| 100 | mariamem prepared | 34.153 / 35.362 | 291.4 / 326.0 |
| 100 | Testcontainers fresh | **N/A: 2 failed attempts** | 4644.5 / 6482.7 † |
| 100 | Testcontainers schema reset | 5.516 / 9.204 | 12.8 / 18.7 |

Each numeric suite cell has three complete repetitions; per-test cells have
30, 150 or 300 observations. † The 100-test fresh-container per-test cell uses
**all 137 completed tests from failed prefixes**, not 100-test completions; its
population is censored by startup failure. Both failures remain in the report.
No failed startup is replaced with a successful latency, and no incomplete suite
is promoted to a passing suite. Schema-reset per-test time excludes its one-time
server startup, which remains included in suite wall time.



## Startup and preparation

First usable SQL in each measured suite, before fixture preparation:

| Condition | Samples | p50 / p95 (ms) |
|---|---:|---:|
| mariamem fresh: initial Start | 9 | 331.7 / 384.6 |
| mariamem prepared: source Start before Snapshot | 9 | 316.8 / 349.3 |
| Testcontainers fresh: first container | 8 | 4192.0 / 5940.7 |
| Testcontainers schema reset: shared server | 9 | 3437.3 / 7782.2 |

The two failed fresh-container suites completed their first startup successfully,
so their first-SQL samples remain included here. Image pulling, Docker Desktop
startup and Go compilation are excluded and documented setup. These numbers do
not mean subsequent container starts always behave like the first one.

At 50 tests, per-test migration/fixture p50/p95 is **5.1/24.9 ms** for fresh
mariamem and **9.3/14.3 ms** for fresh containers. Their empty first-SQL p50/p95
is **306.4/335.2 ms** versus **4557.5/7212.4 ms**. Most of the fresh-server
latency difference is startup, not loading this fixture. Schema reset plus
migration/fixture plus first query takes **11.1/14.1 ms**, once its server exists.

Prepared mariamem performs migration/fixture once (median **5.0 ms**) and Snapshot
once (**427.1 ms**) per suite. At 50 tests, Fork through fixture query is
**295.7/324.8 ms**. Its upfront setup and longer cleanup explain why a modest
per-test readiness improvement does not produce a large suite improvement.
At 100 tests the suite median difference is only **0.30 s**, with overlapping
ranges; this does not establish a strong total-time benefit over fresh Start.

The prepared condition reuses one Snapshot within one Go suite process. The
[final FAST reference](final-v02-local-reference.md) used independently launched
Go trials and measured 374.2/417.7 ms. No production optimization happened between
these measurements; protocol, process lifetime, cache state and local variance
prevent treating this run's lower Fork numbers as another product improvement.
Timing/init diagnostics are OFF; the reused runner takes its existing
public-call timestamps, but the opt-in host/guest recorder is disabled. No new
lifecycle instrumentation or performance tuning was added.

## CPU and memory

CPU seconds, **suite median**, over the recorded suite interval:

| Tests | mariamem fresh: SELF + waited children | mariamem prepared: SELF + waited children | Fresh-container cgroups | Shared-container cgroup |
|---:|---:|---:|---:|---:|
| 10 | 4.14 | 4.74 | 37.40 | 2.34 |
| 50 | 19.86 | 19.25 | 179.16 | 3.84 |
| 100 | 39.93 | 37.67 | N/A: incomplete | 3.13 |

Each mariamem sum is formed **within the same suite**, then summarized; it is not
an addition of independent medians. It includes Go orchestration, Wasmer, setup,
cleanup and local helper children. At 50 tests its Go SELF median is 2.46 s fresh
and 6.53 s prepared: snapshot verification increases host work even though the
prepared path has less observed child CPU. No new architecture inference is made.

Container CPU is summed once per fresh container or read once from the final
shared-container counter; repeated shared snapshots are not added. It includes
entrypoint/database initialization up to the observation, but misses shutdown
and daemon/VM CPU. At 50 tests, additional local runner plus waited-child CPU
is median **7.78 s** fresh and **0.35 s** shared. These scopes do not yield exact
machine-wide apples-to-apples CPU. Observed fresh-container initialization uses
substantially more accounted CPU here; shared-server reuse is much cheaper.

| Condition | Ready DB memory median (MiB) | Component peak observation (MiB) |
|---|---:|---:|
| mariamem fresh | Wasmer RSS 400.5 | waited-child max RSS: median 409.4, max 409.8 |
| mariamem prepared | Wasmer RSS 337.3 | waited-child max RSS: median 394.7, max 408.8 |
| Testcontainers fresh | cgroup usage 137.4 | cgroup memory.peak: median 152.8, max 156.4 |
| Testcontainers schema reset | cgroup usage 139.3 | cgroup memory.peak: median 152.8, max 159.3 |

Ready samples pool all observations, including successful failed-run prefixes.
Go runner max RSS medians are ~20–22 MiB. macOS rusage RSS values are bytes here,
converted to MiB; the waited-child high-water mark includes the prepared source
Start and helpers, not just Fork. It is the maximum child-process footprint, not
a sampled simultaneous process-tree peak. Cgroup memory.peak is read through
ready-time `docker exec`, not after shutdown. Neither measure is a full-machine
peak or unique physical memory; no PSS/private/physical-footprint equivalence is
claimed. Memory does not accumulate 100 DBs: tests are sequential and each DB is
closed. VM resident memory, page cache and shared mappings remain outside a
uniform accounting scheme.

Resource-observer time is retained: at 50 tests it totals ~0.07–0.08 s for each
mariamem suite, ~2.9–3.1 s fresh-container and ~0.08–0.13 s shared-container.
Those times and JSON checkpoints remain inside suite totals; per-test ready
metrics precede them. No unmeasured overhead is silently subtracted.

## Cleanup and limitations

All **33 completed suites** passed fixture identity/mutation isolation checks and
reported successful Close/Terminate calls. Completed mariamem suites observed no
remaining direct Wasmer child; completed container suites had their recorded DB
IDs checked absent. Existing background containers were not targeted. The two
failed startup IDs/termination results were not retained, so the same per-ID
cleanup claim cannot be made for them. No slow measured sample was discarded.

This is sequential isolation, not ×4/×8 parallel scalability or server throughput.
Only a tiny synthetic migration/fixture and a few SQL assertions are exercised;
this is not an ORM, authentication or broad MariaDB-compatibility acceptance.
Versions differ, defaults differ, one side executes in a Docker Linux VM, and
foreground/background load and thermal state were not controlled. Three complete
suite repetitions support descriptive comparisons, not strong tail guarantees.
The repeated fresh-container failure prevents a complete 100-test comparison.

## Where mariamem is better

For the **fresh-server boundary**, the measured 50-test suite median is 17.33 s
fresh or 17.41 s prepared versus 245.47 s fresh containers: ratios of suite medians
are about **14×**, not paired speedup estimates. Initial SQL also arrives much
sooner. The mariamem path does not call Docker; its test DB uses the native
Wasmer bundle and ordinary MySQL driver. Correctly isolated disposable runtimes
work through 100 sequential tests in each completed mariamem suite.

## Where Testcontainers is better

When **schema isolation on a shared server is sufficient**, schema-reset suite
medians are 5.18 s at 50 tests and 5.52 s at 100, versus ~17–34 s for mariamem.
It also has a smaller observed DB memory component here, subject to the different
accounting scopes and excluded VM overhead. Fresh-container startup is not faster
in these observations, and the 100-container condition could not be completed.

Operationally it uses an official native MariaDB server image with ordinary
server configuration/authentication and the existing Testcontainers lifecycle
integration. That is a relevant compatibility/ecosystem property, not proof of
specific ORM compatibility from this benchmark. Its cost is requiring Docker and
VM/image operations on this Mac. mariamem's embedded/WASIX path and default
skip-grant behavior do not simulate every production server environment.

## Prepared-state value

Snapshot/Fork preserves the fixture and prevents test mutations leaking into
later DBs, but **does not materially improve total suite time over fresh
mariamem Start for this ~5 ms fixture**. At 10 tests it is slower; at 50 it is
approximately tied; at 100 the difference is small relative to variation.
Shared-container schema reset is faster for this workload when its weaker
isolation is acceptable. No claim about expensive application migrations or
larger fixtures follows: their amortization was not measured here.

## Product signal

The observations support **Docker-free, disposable real-MariaDB server testing**
when fresh server isolation is needed. Prepared-state reuse is functionally
supported, but this small fixture does not demonstrate an independent large
suite-speed advantage from it. A user who needs only a fresh schema can reasonably
prefer the measured shared-server workflow. The product is not redefined around
these numbers, and the local container failure is not used as a marketing claim.

## Raw evidence

Ignored raw reports and logs remain under `benchmarks/results/`:

- `practical-suites.json` and its per-suite files: original full attempt;
  SHA256 `eb70fcd9d29ed1907e051540aa0af7acb1b32907a526a512cb9ae1c6287e08bf`.
- `practical-suites-100-retry.json` and per-suite files: unchanged repeat, including
  the second failure; SHA256 `df64210aab04005d4ea5f937c67523a7bdf1fe98a46d67c930cde4a28f9c3780`.
- `practical-suites-100-complement-*.json` / `.log`: five bounded complement suites.
- `practical-suites-analysis.json`: consolidated environment, artifact identities,
  dataset hashes and all 43 trials (33 completed measured suites, two failed
  measured suites, eight labelled warmups); explicitly marked partial.

The original and repeat aggregate `completed` flags remain **false**. Their
failure is not overridden by documentation or by completion of other conditions.
Raw samples and exact environment/artifact identities permit later reanalysis;
only the harness and this analysis/documentation are committed.
