# Post-InnoDB plugin initialization attribution

This follows [the initialization investigation](mariadb-init-investigation.md).
It is measurement on main, not a plugin/cache optimization or an architecture
experiment. **Completed evidence:** [run 36282549967](https://github.com/masahitojp/mariamem/actions/runs/36282549967),
source `57926f24764868d1279bb2b1fbb65c52d33e704a`.
The dominant latency belongs to `caching_sha2_password`, while Aria owns the
large observed mapping increment. These are separate costs.

## Established measurement and open question

**Previous measured fact:** at ×1 the interval from `srv_start()` returning to
`plugins_complete` occupies roughly 90% of embedded init, with p50 650 ms on
macOS and 636 ms on Ubuntu. Its p50 grows to 1544/2140 ms at ×8. Approximately
126 MiB of wrapped mapping growth occurs in the interval. Those observations
are from the earlier source/run, not the newly instrumented guest.

**Resolved by this probe:** Aria cache construction accounts for the mapping
growth, but not the dominant CPU time. Numerical similarity alone would have
led to the wrong latency experiment. The tables below measure both independently.

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
Runtime callback events identify what actually initializes eagerly. Both platforms observed the same 70 callback invocations in the same order in
every measured sample, with 69 distinct names (`uuid` appears twice). Named
callback summaries aggregate both invocations where names coincide. The source-tree inventory alone is not evidence that a plugin initialized.

| Component | Eagerness/source evidence | Significant allocation / semantic relevance |
| --- | --- | --- |
| InnoDB | Observed eager in previous run; split successful callback | 16 MiB configured buffer pool; real transactions/recovery. Disabling changes product behavior. |
| Aria | Observed eager callback, directly measured | 128 MiB main / 2 MiB log cache defaults; engine, recovery and potentially internal temporary tables. Shrinking is a candidate setting experiment, not a proven semantic-neutral change. |
| MyISAM | Global key cache eagerly prepared before plugins; separate engine callback | Large default key-cache budget; MyISAM tables and related engines may rely on it. Callback alone is not full allocation cost. |
| mhnsw / VECTOR_INDEXES | Mandatory built-in descriptors in `sql_builtin.cc.in` | Source registers a transaction participant, options and information-schema hooks; vector graph caches also have later per-index paths. Observed callbacks have zero wrapped mapping growth and tiny duration. Removing changes vector/index metadata functionality. |
| binlog / native password plugins | Mandatory built-in descriptors | Transaction participant/authentication functionality; registration does not imply binary logging is enabled. Measured tiny compared with the authentication callback. |
| MEMORY, CSV, MERGE, partition and metadata plugins | All listed engines observed eager, plus named metadata callbacks | Engine/table and information-schema semantics; no startup budget guessed. Measured callbacks are small; no plugin is removed. |

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

**Remaining blind spots:** process-wide counters include concurrent background
work; plugin callbacks exclude framework/status tails; logical file wrappers
miss libc-internal I/O/mmap; allocation deltas are not physical/private RAM;
CPU does not separate allocator/zeroing/page faults; hosted concurrency is not
an equivalent-hardware cross-platform comparison. Disabled diagnostics still
carry a small static collector/code footprint, so comparison with older guests
is not an instrumentation-free causal control.

## Verified measurement identity

ZIP hashes equal the GitHub artifact digests:

- macOS: `12883d50befbbabec1276838e29630d1fbb5d74da88fb0b195404155b96038be`
- Ubuntu: `8c2f04f061df379d3e2558fdddb6b50bf736b39ea0e9804901f712c9f9088ae3`
- guest: `8988451aeddc70060625641f14bf53e9e26fe47062d854c9f6ea6057f2e07b60`

The common WASM bytes, seal, original checkout/input identity and provenance
passed `benchmark_artifacts.verify_wasm`; SHA256 is
`28fee71ea4cd97af117e56a5eaea8fc71540ff820623e4cc22a567a375282ab8`.
Both reports completed, named the exact measured commit, and recomputed
initialization summaries matched saved summaries. Validation checks all raw
boundaries and rejects dropped records. Recorded AOT hashes match native
manifests: macOS `5d9616bb16184b1fbb7a6b155bb0bdf4ebe62ca6d658dd4ad580f0d6c2471101`;
Ubuntu `c7b66f525606dec9ce97da4035dfed02e3ae082ea18c9b86fee1735350e3b212`.
The measurement ZIPs contain AOT records/manifest, not the AOT binary itself;
these records were cross-checked, not rehashed from absent binaries.

Environment: macOS 15.7.9 arm64, three reported CPUs; Ubuntu 24.04 x86_64,
kernel 6.17.0-1022-azure/glibc 2.39, four reported CPUs; Go 1.26.8, summary
Python 3.14.7, Wasmer 7.4.2 and MariaDB 13.1.0-embedded. Twenty batches after two
warmups produce 20/80/160 correlated per-DB observations at ×1/4/8.
Absolute platform latency is not a same-hardware comparison. No 100,000-row
repeat was needed to locate the new dominant callback; this run does not establish
fixture-size sensitivity of RSA generation.

The guest and both AOT stages were REBUILT on this first instrumented run, then
saved as verified caches. Guest build/seal took 10m36s, AOT compile/seal 18–19s.
This run establishes cache creation, not a measured cache-hit speedup.

## Stage wall and CPU results

All values below are **p50 / p95 ms**, per DB. Scopes overlap; percentile
values are not additive. The callback end excludes later status registration.

### macOS: wall time

| Stage | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| complete embedded initialization | 884.780 / 2483.014 | 1067.782 / 2053.216 | 1866.399 / 3207.715 |
| post-srv_start plugins | 813.763 / 2427.280 | 926.071 / 1825.235 | 1557.087 / 2911.457 |
| plugin caching_sha2_password callback | 801.863 / 2418.955 | 916.827 / 1787.260 | 1525.149 / 2901.034 |
| remaining InnoDB after srv_start | 0.065 / 0.151 | 0.085 / 3.567 | 0.067 / 3.509 |
| Aria enclosing init | 8.121 / 13.225 | 8.493 / 24.301 | 8.444 / 84.963 |
| Aria main page cache | 0.408 / 0.738 | 0.609 / 4.471 | 0.452 / 3.999 |
| Aria log page cache | 0.025 / 0.049 | 0.022 / 0.095 | 0.015 / 0.041 |
| Aria log initialization | 0.312 / 0.740 | 0.912 / 3.966 | 1.071 / 14.626 |
| Aria recovery | 0.466 / 1.303 | 0.484 / 2.375 | 0.396 / 2.416 |
| Aria checkpoint | 6.945 / 11.069 | 4.506 / 16.904 | 4.588 / 61.702 |
| MyISAM key cache | 1.655 / 4.560 | 2.618 / 16.907 | 1.815 / 23.145 |
| plugin MyISAM callback | 0.017 / 0.027 | 0.018 / 0.045 | 0.018 / 0.044 |
| plugin mhnsw callback | 0.009 / 0.016 | 0.010 / 0.032 | 0.009 / 0.030 |

macOS authentication callback CPU:

| DBs | Process CPU p50 / p95 ms | Current-thread CPU p50 / p95 ms |
| --- | ---: | ---: |
| 1 | 801.77 / 2426.53 | 786.94 / 2413.86 |
| 4 | 661.47 / 1450.07 | 661.04 / 1449.16 |
| 8 | 586.08 / 1571.75 | 583.62 / 1569.98 |

### Ubuntu: wall time

| Stage | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| complete embedded initialization | 730.124 / 1941.740 | 1065.087 / 1885.279 | 2073.496 / 3396.633 |
| post-srv_start plugins | 651.383 / 1865.857 | 939.149 / 1732.922 | 1901.699 / 3183.476 |
| plugin caching_sha2_password callback | 641.024 / 1856.501 | 906.905 / 1704.075 | 1841.712 / 3152.047 |
| remaining InnoDB after srv_start | 0.039 / 0.136 | 0.034 / 1.248 | 0.033 / 0.971 |
| Aria enclosing init | 9.461 / 10.806 | 31.103 / 49.673 | 41.589 / 86.949 |
| Aria main page cache | 0.584 / 1.293 | 1.213 / 4.301 | 1.234 / 5.981 |
| Aria log page cache | 0.055 / 0.068 | 0.057 / 0.151 | 0.057 / 1.403 |
| Aria log initialization | 0.711 / 1.109 | 0.664 / 3.262 | 0.663 / 4.570 |
| Aria recovery | 1.445 / 2.133 | 3.223 / 7.126 | 5.970 / 11.063 |
| Aria checkpoint | 5.503 / 7.808 | 23.538 / 41.503 | 32.058 / 76.180 |
| MyISAM key cache | 1.511 / 2.162 | 2.462 / 3.711 | 2.609 / 7.689 |
| plugin MyISAM callback | 0.006 / 0.006 | 0.008 / 0.010 | 0.009 / 0.027 |
| plugin mhnsw callback | 0.004 / 0.004 | 0.006 / 0.008 | 0.006 / 0.023 |

Ubuntu authentication callback CPU:

| DBs | Process CPU p50 / p95 ms | Current-thread CPU p50 / p95 ms |
| --- | ---: | ---: |
| 1 | 641.14 / 1857.82 | 641.00 / 1856.31 |
| 4 | 839.19 / 1611.73 | 838.53 / 1595.42 |
| 8 | 921.41 / 2163.29 | 920.40 / 2162.02 |

**Measured fact:** authentication initialization is CPU-heavy at ×1 on both
platforms and is the largest absolute wall-time increase at ×8. Aria's main
cache is sub-millisecond at ×1 and only ~0.5–1.2 ms p50 at ×8. Aria's enclosing
init grows more on Ubuntu (9.5 → 41.6 ms), but remains small relative to the
1.84-second authentication callback. Remaining InnoDB callback work is tiny.
Vector initialization is not the hidden large cache/CPU bucket.

**Derived calculation:** median per-sample share of the post-`srv_start` interval
in `caching_sha2_password` is macOS 98.62 / 98.87 / 99.24%, Ubuntu
98.41 / 96.75 / 97.68% at ×1/4/8. Clipping each successful callback to that
interval and subtracting their summed durations per sample leaves framework /
unattributed wall p50 of macOS 0.246 / 0.281 / 0.248 ms and Ubuntu
0.277 / 0.336 / 0.348 ms. These are calculated residuals, not new clocks or
subtractions of medians. They include instrumentation/framework gaps.

At ×8 authentication wall substantially exceeds per-DB process/thread CPU.
This supports CPU scheduling/resource competition under isolation parallelism;
it does not identify a lock, allocator or page-fault cause. Broad p95 values
also exist at ×1, so concurrency alone does not explain the variance.

## Memory/cache ownership and file observations

**Measured function-window attribution, identical mapping deltas across the
observed concurrency cases on both platforms:**

| Scope | Wrapped mapping growth MiB | Typical wrapped C balance delta MiB |
| --- | ---: | ---: |
| MyISAM key-cache construction, before plugins | 112.083 | 15.92 |
| Aria main page-cache construction | 124.227 | 3.77 |
| Aria log page-cache construction | 1.930 | 0.063 |
| Aria enclosing initialization | 126.156 | ~12–20, varies with background allocation |
| caching_sha2_password callback | 0 | ~0.03 net at ×1; not an allocation-churn measure |

**Source + derived finding:** Aria's `multi_init_pagecache` / `init_pagecache`
constructs page buffers via `my_large_malloc`; main and log cache mapping deltas
sum to the enclosing 126.156 MiB increase. This identifies the cache-owning
construction window, rather than relying on the default's numerical similarity.
The 128 MiB budget includes buffer/metadata overhead, so it is not itself the
mapped block size. The MyISAM cache's separate 112 MiB growth precedes plugin
init. Neither large mapping construction explains the dominant latency.

Mapping length is not committed/private RAM. Unchanged wrapped balances inside
RSA init do not imply no temporary crypto allocation. Global counters can include
background threads; exact object addresses and physical page ownership remain
unmeasured. No cache resize has been tested for SQL/resource correctness.

Direct read/write counters are small inside authentication (typically zero,
with occasional background activity), with no large file transfer explaining
its CPU time. BIO/file I/O and paths outside `/mariadb` are not fully observed.
Aria main-cache window p50 read/write is 0/0 MiB on macOS and 0.016/0.141 MiB on
Ubuntu; these can include background activity. Aria log init is ~0.008/0 MiB on
macOS and 0.274/0.336 MiB on Ubuntu; Aria recovery is ~0/0 and 0.539/0 MiB.
Summed direct I/O call times are milliseconds, not the hundreds of ms in auth.

Sampled group peak runtime RSS p50 (MiB) is macOS 339 / 1370 / 2225 and Ubuntu
409 / 1617 / 3216 at ×1/4/8. This run has no OS mapping-capture attribution;
shared mappings and sampling/pressure affect RSS. Ubuntu sampled `ps` CPU has
whole-second granularity (×1 median zero), so stage guest CPU clocks are the
stronger evidence for this callback's work. No per-stage RSS is invented.

## Actual eager plugin inventory and semantic relevance

Both platforms show the same initialization sequence: MyISAM and core type/
function/participant callbacks; MEMORY/CSV; InnoDB; Aria; MERGE/partition/
sequence; information-schema/statistics callbacks; finally authentication
(`caching_sha2_password`, `mysql_native_password`, `parsec`, `mysql_old_password`).
`uuid` is invoked twice. The 70 invocations fit the bounded collector with no
loss. The metadata/type/function callbacks are generally microseconds, not the
hundreds-of-ms bucket. Raw events retain exact names and ordering.

Observed groups include `mhnsw`, `VECTOR_INDEXES`, `binlog`, XML/INET/UUID,
`sys_refcursor`, `associative_array`, `sys_guid`, SQL/engine sequence and
`user_variables`; CLIENT/INDEX/TABLE/USER_STATISTICS, GEOMETRY_COLUMNS,
SPATIAL_REF_SYS and InnoDB information-schema families (FT, CMP, buffer, SYS,
transaction/lock, metrics and encryption views). These expose real SQL, vector,
authentication and metadata functionality; eager observation does not mean all
features are used by the benchmark or safe to remove.

**Source fact resolving the expensive callback:**
`plugin/auth_mysql_sha2/mysql_sha2.c::init_keys()` conditionally calls
`ssl_genkeys()` when default key paths are used, both files are absent, and
`auto_generate_rsa_keys` (default true) is enabled; it then calls `ssl_loadkeys()`.
`ssl_stuff.c::ssl_genkeys()` calls `EVP_RSA_gen(2048)` and writes PEM private/public
keys. Its compatibility implementation invokes EVP RSA key generation.

**Strong hypothesis:** repeated RSA-2048 generation explains most callback CPU
and variable latency. The measured callback has no other large initialization
branch in this source, but generation versus loading/access/error handling was
not individually timed; actual selected key-path branch is not recorded. Zero
wrapped I/O does not prove generation or successful key persistence. Do not
claim a directly measured RSA-only timer or prime-search attribution.

RSA key handling supports `caching_sha2_password` full authentication, including
password protection when a suitable secure transport is unavailable. Disabling
this plugin/key support can change which clients/accounts work; ordinary
benchmark SQL using another authentication mode cannot establish equivalence.
Existing configured key material could avoid generation while retaining the
plugin, but key location/persistence, error handling, security expectations and
snapshot/isolation treatment must be tested. Shrinking Aria is a separate memory
question, no longer the first latency hypothesis.

## Recommended first experiment

On a disposable experiment branch, retain all plugins and cache sizes, provide
an explicit valid **test-only RSA-2048 key pair** through the existing configured
private/public key paths, and compare against missing/default paths. Verify
that loading succeeds and cover `caching_sha2_password` authentication as well
as ordinary SQL, Snapshot/Fork and independent state. Never treat shared test
keys as a production security policy or disable authentication to gain speed.

Measure the same callback and Fork ×1/4/8 with interleaved controls, using exact
artifacts. This is the smallest experiment that discriminates repeated key
generation from required engine startup without continuation, VFS or plugin
removal. If the callback remains expensive with confirmed pre-existing keys,
split only its generation/load/crypto branch next. No experiment or optimization
is implemented here; choosing the 0.2 architecture remains premature.
