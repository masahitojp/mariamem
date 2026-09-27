# Post-InnoDB plugin initialization attribution

This follows [the initialization investigation](mariadb-init-investigation.md).
It is measurement on main, not a plugin/cache optimization or an architecture
experiment. New per-plugin measurements are **pending the focused CI run**;
source facts below are not measured timings or proof of an Aria bottleneck.

## Established measurement and open question

**Previous measured fact:** at ×1 the interval from `srv_start()` returning to
`plugins_complete` occupies roughly 90% of embedded init, with p50 650 ms on
macOS and 636 ms on Ubuntu. Its p50 grows to 1544/2140 ms at ×8. Approximately
126 MiB of wrapped mapping growth occurs in the interval. Those observations
are from the earlier source/run, not the newly instrumented guest.

**Unknown:** whether Aria's cache owns this growth or most CPU time. Numerical
similarity to a 128 MiB cache is insufficient. This probe isolates the function
that constructs that cache and inventories every actual plugin callback.

## Source sequence and instrumented boundaries

The pinned source is prepared by `prepare_guest.py`; fail-closed hooks in
`guest_init_hooks.py` enter the recorded modified-source provenance. No change
to `guest/source.patch`, SQL options, cache sizes or plugin selection is made.

1. `init_server_components()` initializes key caches through
   `process_key_caches(&ha_init_key_cache, 0)` **before** `plugin_init()`. The
   `myisam_key_cache_begin/complete` interval measures this separately; MyISAM's
   later handlerton callback is not the large key-cache construction itself.
2. `plugin_init()` registers built-ins, resolves options/dependencies and calls
   `plugin_do_initialize()`. A bounded `plugin.<actual-name>.begin/end` pair
   measures each successful initialization callback/type wrapper. Raw event
   order is the authoritative inventory; no hard-coded order among engines is
   assumed. Status-variable registration after callback success remains outside
   these pairs, within the enclosing plugin framework scope.
3. InnoDB's callback runs `srv_start()`, then parameter adjustment, LRU ratio,
   mutex/counter/monitor setup. `innodb_start_complete` to
   `plugin.InnoDB.end` measures this tail plus the type wrapper's return work.
4. `ha_maria_init()` performs setup/upgrade/init/control-file work, constructs
   the main segmented Aria page cache, constructs the log page cache, initializes
   translog, recovers logs, initializes checkpointing, and finishes handlerton
   hooks. Separate markers bracket these existing calls.
5. Other actual plugin callbacks and the enclosing `plugins_complete` marker
   expose whether the cost is distributed or remains in framework/unattributed
   work. Subtract intervals **per sample**, never subtract aggregated medians;
   successful callback intervals exclude separately reported failed attempts and
   status-registration tails.

| New reported stage | Source-owned scope |
| --- | --- |
| MyISAM key cache | `process_key_caches` / `ha_init_key_cache` |
| Remaining InnoDB after srv_start | Successful InnoDB callback tail/type wrapper |
| Aria setup/control | Handlerton setup, upgrade, `maria_init`, control file |
| Aria main page cache | `multi_init_pagecache`, including block buffers/metadata |
| Aria log page cache | `init_pagecache(maria_log_pagecache, ...)` |
| Aria log initialization | `translog_init` |
| Aria recovery | Recovery/mark-success branch |
| Aria checkpoint / remaining setup | `ma_checkpoint_init`, final hook assignment |
| Each plugin callback | Actual callback/type wrapper, named by the built-in descriptor |

**Source facts:** Aria's main cache defaults to `KEY_CACHE_SIZE` (128 MiB).
`init_pagecache()` computes a buffer/metadata budget, calls `my_large_malloc`
for page buffers and `my_multi_malloc_large(... MY_ZEROFILL ...)` for metadata.
The log cache is separately configured as `TRANSLOG_PAGECACHE_SIZE` (2 MiB).
MyISAM's key-cache allocation also uses `my_large_malloc`, in a different scope.
These call sites give an ownership hypothesis for mapping growth, not a result.

## Plugin inventory and semantic relevance

The build-generated `sql_builtin.cc` determines optional linked engines.
Runtime callback events identify what actually initializes eagerly. The exact
observed list and costs must be filled from the new report, not inferred solely
from plugins present in the source tree.

| Component | Eagerness/source evidence | Significant allocation / semantic relevance |
| --- | --- | --- |
| InnoDB | Observed eager in previous run; split successful callback | 16 MiB configured buffer pool; real transactions/recovery. Disabling changes product behavior. |
| Aria | Existing init/recovery source path; new markers require this enabled path | 128 MiB main / 2 MiB log cache defaults; engine, recovery and potentially internal temporary tables. Shrinking is a candidate setting experiment, not a proven semantic-neutral change. |
| MyISAM | Global key cache eagerly prepared before plugins; separate engine callback | Large default key-cache budget; MyISAM tables and related engines may rely on it. Callback alone is not full allocation cost. |
| mhnsw / VECTOR_INDEXES | Mandatory built-in descriptors in `sql_builtin.cc.in` | Source registers a transaction participant, options and information-schema hooks; vector graph caches also have later per-index paths. No measured eager 128 MiB allocation is established here. Removing changes vector/index metadata functionality. |
| binlog / native password plugins | Mandatory built-in descriptors | Transaction participant/authentication functionality; registration does not imply binary logging is enabled. Cost pending. |
| MEMORY, CSV, MERGE, partition and metadata plugins | Optional compiled/active membership requires runtime inventory | Engine/table and information-schema semantics; no startup budget guessed. Callback cost will be measured for any initialized member. |

`mysqld.cc` explicitly refuses startup without Aria when built with
`USE_ARIA_FOR_TMP_TABLES` (outside bootstrap). Whether this exact build defines
that option is a build-configuration fact still to verify; an InnoDB-only test
fixture does not establish that Aria is dispensable. Shrinking/removing caches
may affect resource behavior, query plans, spills, errors or supported SQL.
Nothing is disabled or resized by this probe.

## Measurement and interpretation

The focused `guest-build-boundary.yml` input `plugin_measurement=true` uses the
canonical Go API benchmark, 20 measured batches / 2 warmups, 1,000 rows and
workers 1/4/8, on macOS 15 arm64 and Ubuntu 24.04 x86_64. It excludes the larger
fixture, mapping-capture/control/reuse suites and unrelated release acceptance.

Instrumentation changes guest inputs, so the common WASM rebuilds once, with
one dependent AOT per platform. Subsequent unchanged-input runs use the existing
verified immutable cache path. Raw output `init-plugins.json` retains every
sample and counter; `init-plugins.md` reports stage wall/process/current-thread
CPU p50/p95 and allocation/mapping/read/write observations. CI artifacts are
`initialization-<platform>-<commit>`; raw results stay ignored.

Counters remain opt-in. Plugin labels are copied into a bounded 256-event
collector; truncation/overflow is reported as incomplete data and rejected.
Aria markers insert false operands into the existing short-circuit OR chain:
function calls, failure conditions and ordering are unchanged. Failed/retried
callbacks retain a separate `.failed` boundary; they are not reported as zero-cost
successes. There is no general tracing or plugin-control framework.

**Required measured answers after the run:** stage p50/p95 and CPU/mapping deltas
at ×1/4/8; per-sample fraction of the dominant interval in each plugin/cache;
actual callback inventory; whether ~126 MiB growth lands in main-cache creation;
whether that same scope accounts for substantial CPU and concurrency growth.
None of these new numerical results is available before CI finishes.

**Remaining blind spots:** process-wide counters include concurrent background
work; plugin callbacks exclude framework/status tails; logical file wrappers
miss libc-internal I/O/mmap; allocation deltas are not physical/private RAM;
CPU does not separate allocator/zeroing/page faults; hosted concurrency is not
an equivalent-hardware cross-platform comparison. Disabled diagnostics still
carry a small static collector/code footprint, so comparison with older guests
is not an instrumentation-free causal control.

## Recommended first experiment

No cache or continuation experiment is selected before these measurements.
First resolve the paired questions: **which callback owns elapsed CPU, and which
cache call owns mapping growth?** If the main Aria cache explains both, the
smallest subsequent experiment is a disposable branch varying only that cache
budget while preserving plugin selection/recovery and checking SQL/temporary-
table correctness. If those costs separate, investigate the measured dominant
callback instead. Do not infer that continuation is necessary from the current
unattributed interval, and do not implement either experiment in this task.
